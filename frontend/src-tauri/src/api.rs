use reqwest::{header, redirect, Method, StatusCode, Url};
use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::{json, Value};
use std::{env, net::IpAddr, sync::Arc, time::Duration};
use tauri::State;
use tokio::sync::Mutex;

const DEFAULT_ORIGIN: &str = "http://127.0.0.1:8000/api/v1";
const REQUEST_LIMIT: usize = 256 * 1024;
const RESPONSE_LIMIT: usize = 2 * 1024 * 1024;

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BridgeError {
    kind: &'static str,
    message: String,
    status: Option<u16>,
    code: Option<String>,
    request_id: Option<String>,
}

impl BridgeError {
    fn local(kind: &'static str, message: impl Into<String>) -> Self {
        Self { kind, message: message.into(), status: None, code: None, request_id: None }
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BridgeStatus {
    available: bool,
    origin: Option<String>,
    error: Option<BridgeError>,
}

#[derive(Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct LoginInput {
    email: String,
    password: String,
}

#[derive(Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterInput {
    email: String,
    password: String,
    display_name: String,
}

#[derive(Clone, Deserialize, Serialize)]
struct UserResponse {
    id: String,
    email: String,
    display_name: String,
    is_active: bool,
    #[serde(default)]
    profile: Value,
    created_at: String,
    updated_at: String,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UserView {
    id: String,
    email: String,
    display_name: String,
    is_active: bool,
}

impl From<UserResponse> for UserView {
    fn from(value: UserResponse) -> Self {
        Self { id: value.id, email: value.email, display_name: value.display_name, is_active: value.is_active }
    }
}

#[derive(Deserialize)]
struct TokenResponse {
    access_token: String,
    refresh_token: String,
}

#[derive(Deserialize)]
struct AuthResponse {
    user: UserResponse,
    tokens: TokenResponse,
}

#[derive(Deserialize)]
struct RefreshResponse {
    tokens: TokenResponse,
}

#[derive(Deserialize)]
struct ReadinessResponse {
    status: String,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReadinessView {
    ready: bool,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
enum RadarType {
    Academic,
    Business,
    Technology,
    Market,
    Policy,
    Competitive,
    Custom,
    Opportunity,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
enum ResourceStatus {
    Active,
    Paused,
    Archived,
}

#[derive(Clone, Deserialize)]
struct RadarResponse {
    id: String,
    name: String,
    description: Option<String>,
    goal: String,
    radar_type: RadarType,
    categories: Vec<String>,
    keywords: Vec<String>,
    status: ResourceStatus,
    notification_threshold: i64,
}

#[derive(Deserialize)]
struct RadarPage {
    items: Vec<RadarResponse>,
    page: i64,
    page_size: i64,
    total: i64,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RadarCreateInput {
    name: String,
    goal: String,
    radar_type: RadarType,
    description: Option<String>,
}

impl RadarCreateInput {
    fn payload(mut self) -> Result<Vec<u8>, BridgeError> {
        self.name = self.name.trim().to_string();
        self.goal = self.goal.trim().to_string();
        if !(1..=120).contains(&self.name.chars().count()) || !(1..=4000).contains(&self.goal.chars().count()) {
            return Err(BridgeError::local("invalid_input", "Radar name or goal is outside the allowed length"));
        }
        self.description = self.description.and_then(|value| {
            let value = value.trim().to_string();
            if value.is_empty() { None } else { Some(value) }
        });
        let value = json!({ "name": self.name, "goal": self.goal, "radar_type": self.radar_type, "description": self.description });
        serde_json::to_vec(&value).map_err(|_| BridgeError::local("invalid_input", "Radar request could not be encoded"))
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RadarView {
    id: String,
    name: String,
    description: Option<String>,
    goal: String,
    radar_type: RadarType,
    categories: Vec<String>,
    keywords: Vec<String>,
    status: ResourceStatus,
    notification_threshold: i64,
}

impl From<RadarResponse> for RadarView {
    fn from(value: RadarResponse) -> Self {
        Self {
            id: value.id,
            name: value.name,
            description: value.description,
            goal: value.goal,
            radar_type: value.radar_type,
            categories: value.categories,
            keywords: value.keywords,
            status: value.status,
            notification_threshold: value.notification_threshold,
        }
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RadarPageView {
    items: Vec<RadarView>,
    page: i64,
    page_size: i64,
    total: i64,
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionView {
    authenticated: bool,
    user: Option<UserView>,
}

struct Session {
    generation: u64,
    access_token: Option<String>,
    refresh_token: Option<String>,
    user: Option<UserView>,
}

impl Session {
    fn empty() -> Self {
        Self { generation: 0, access_token: None, refresh_token: None, user: None }
    }

    fn clear_and_fence(&mut self) {
        self.generation = self.generation.wrapping_add(1);
        self.access_token = None;
        self.refresh_token = None;
        self.user = None;
    }

    fn view(&self) -> SessionView {
        SessionView { authenticated: self.access_token.is_some(), user: self.user.clone() }
    }
}

#[derive(Clone, Copy)]
enum Operation {
    Register,
    Login,
    Refresh,
    Logout,
    Me,
    Ready,
    Radars,
    RadarCreate,
}

impl Operation {
    fn method(self) -> Method {
        match self {
            Self::Register | Self::Login | Self::Refresh | Self::Logout | Self::RadarCreate => Method::POST,
            Self::Me | Self::Ready | Self::Radars => Method::GET,
        }
    }

    fn path(self) -> &'static str {
        match self {
            Self::Register => "auth/register",
            Self::Login => "auth/login",
            Self::Refresh => "auth/refresh",
            Self::Logout => "auth/logout",
            Self::Me => "users/me",
            Self::Ready => "health/ready",
            Self::Radars => "radars?page=1&page_size=100",
            Self::RadarCreate => "radars",
        }
    }
}

struct HttpResponse {
    status: StatusCode,
    body: Vec<u8>,
}

#[derive(Clone)]
struct ApiClient {
    base: Url,
    http: reqwest::Client,
    session: Arc<Mutex<Session>>,
}

impl ApiClient {
    fn new(origin: &str) -> Result<Self, BridgeError> {
        let base = validate_origin(origin)?;
        let http = reqwest::Client::builder()
            .redirect(redirect::Policy::none())
            .no_proxy()
            .connect_timeout(Duration::from_secs(5))
            .timeout(Duration::from_secs(15))
            .user_agent("FlowTracer-Desktop/0.1")
            .build()
            .map_err(|_| BridgeError::local("client_setup", "Desktop HTTP client could not be initialized"))?;
        Ok(Self { base, http, session: Arc::new(Mutex::new(Session::empty())) })
    }

    fn safe_origin(&self) -> String {
        self.base.as_str().trim_end_matches('/').to_string()
    }

    async fn send(&self, operation: Operation, body: Option<Vec<u8>>, access_token: Option<&str>) -> Result<HttpResponse, BridgeError> {
        if body.as_ref().is_some_and(|value| value.len() > REQUEST_LIMIT) {
            return Err(BridgeError::local("request_too_large", "Request exceeds the desktop bridge limit"));
        }
        let url = self.base.join(operation.path()).map_err(|_| BridgeError::local("path_denied", "Operation path is not permitted"))?;
        if url.scheme() != self.base.scheme() || url.host_str() != self.base.host_str() || url.port_or_known_default() != self.base.port_or_known_default() {
            return Err(BridgeError::local("origin_denied", "Operation left the configured API origin"));
        }
        let mut request = self.http.request(operation.method(), url).header(header::ACCEPT, "application/json");
        if let Some(token) = access_token {
            request = request.bearer_auth(token);
        }
        if let Some(payload) = body {
            request = request.header(header::CONTENT_TYPE, "application/json").body(payload);
        }
        let mut response = request.send().await.map_err(|_| BridgeError::local("network", "Desktop bridge request failed"))?;
        let status = response.status();
        if status.is_redirection() {
            return Err(BridgeError { kind: "redirect_denied", message: "API redirects are not permitted".into(), status: Some(status.as_u16()), code: None, request_id: None });
        }
        if response.content_length().is_some_and(|length| length > RESPONSE_LIMIT as u64) {
            return Err(BridgeError { kind: "response_too_large", message: "Response exceeds the desktop bridge limit".into(), status: Some(status.as_u16()), code: None, request_id: None });
        }
        let mut bytes = Vec::new();
        while let Some(chunk) = response.chunk().await.map_err(|_| BridgeError::local("network", "Desktop bridge response was interrupted"))? {
            if bytes.len().saturating_add(chunk.len()) > RESPONSE_LIMIT {
                return Err(BridgeError { kind: "response_too_large", message: "Response exceeds the desktop bridge limit".into(), status: Some(status.as_u16()), code: None, request_id: None });
            }
            bytes.extend_from_slice(&chunk);
        }
        Ok(HttpResponse { status, body: bytes })
    }

    fn require_success<T: DeserializeOwned>(&self, response: HttpResponse) -> Result<T, BridgeError> {
        if !response.status.is_success() {
            return Err(remote_error(response));
        }
        serde_json::from_slice(&response.body).map_err(|_| BridgeError { kind: "invalid_response", message: "Backend returned an invalid response".into(), status: Some(response.status.as_u16()), code: None, request_id: None })
    }

    async fn authenticate(&self, operation: Operation, email: String, mut password: String, display_name: Option<String>) -> Result<SessionView, BridgeError> {
        if email.trim().is_empty() || password.is_empty() {
            return Err(BridgeError::local("invalid_input", "Email and password are required"));
        }
        let generation = {
            let mut session = self.session.lock().await;
            session.clear_and_fence();
            session.generation
        };
        let value = if let Some(name) = display_name {
            json!({ "email": email, "password": password, "display_name": name })
        } else {
            json!({ "email": email, "password": password })
        };
        let payload = serde_json::to_vec(&value).map_err(|_| BridgeError::local("invalid_input", "Authentication request could not be encoded"))?;
        password.clear();
        drop(value);
        let response = self.send(operation, Some(payload), None).await?;
        let auth: AuthResponse = self.require_success(response)?;
        let mut session = self.session.lock().await;
        if session.generation != generation {
            return Err(BridgeError::local("stale_session", "Session changed while authentication was in flight"));
        }
        session.access_token = Some(auth.tokens.access_token);
        session.refresh_token = Some(auth.tokens.refresh_token);
        session.user = Some(auth.user.into());
        Ok(session.view())
    }

    async fn refresh_locked(&self, generation: u64, failed_access: Option<&str>) -> Result<String, BridgeError> {
        let mut session = self.session.lock().await;
        if session.generation != generation {
            return Err(BridgeError::local("stale_session", "Session changed while request was in flight"));
        }
        if let (Some(failed), Some(current)) = (failed_access, session.access_token.as_deref()) {
            if failed != current {
                return Ok(current.to_string());
            }
        }
        let refresh = session.refresh_token.clone().ok_or_else(|| BridgeError::local("authentication_required", "Sign in is required"))?;
        let payload = serde_json::to_vec(&json!({ "refresh_token": refresh })).map_err(|_| BridgeError::local("invalid_input", "Refresh request could not be encoded"))?;
        let response = self.send(Operation::Refresh, Some(payload), None).await?;
        if !response.status.is_success() {
            let error = remote_error(response);
            if error.status == Some(401) {
                session.clear_and_fence();
            }
            return Err(error);
        }
        let refreshed: RefreshResponse = serde_json::from_slice(&response.body).map_err(|_| BridgeError::local("invalid_response", "Backend returned an invalid refresh response"))?;
        session.access_token = Some(refreshed.tokens.access_token.clone());
        session.refresh_token = Some(refreshed.tokens.refresh_token);
        Ok(refreshed.tokens.access_token)
    }

    async fn protected_with_body_and_generation<T: DeserializeOwned>(&self, operation: Operation, body: Option<Vec<u8>>) -> Result<(T, u64), BridgeError> {
        let (generation, access) = {
            let session = self.session.lock().await;
            (session.generation, session.access_token.clone().ok_or_else(|| BridgeError::local("authentication_required", "Sign in is required"))?)
        };
        let first = self.send(operation, body.clone(), Some(&access)).await?;
        let response = if first.status == StatusCode::UNAUTHORIZED {
            let refreshed = self.refresh_locked(generation, Some(&access)).await?;
            self.send(operation, body, Some(&refreshed)).await?
        } else {
            first
        };
        let result = self.require_success(response)?;
        let session = self.session.lock().await;
        if session.generation != generation {
            return Err(BridgeError::local("stale_session", "Session changed while request was in flight"));
        }
        Ok((result, generation))
    }

    async fn protected_with_generation<T: DeserializeOwned>(&self, operation: Operation) -> Result<(T, u64), BridgeError> {
        self.protected_with_body_and_generation(operation, None).await
    }

    async fn protected<T: DeserializeOwned>(&self, operation: Operation) -> Result<T, BridgeError> {
        self.protected_with_generation(operation).await.map(|(result, _)| result)
    }

    async fn remember_user(&self, generation: u64, view: UserView) -> Result<UserView, BridgeError> {
        let mut session = self.session.lock().await;
        if session.generation != generation || session.access_token.is_none() {
            return Err(BridgeError::local("stale_session", "Session changed while request was in flight"));
        }
        session.user = Some(view.clone());
        Ok(view)
    }

    async fn current_user(&self) -> Result<UserView, BridgeError> {
        let (user, generation): (UserResponse, u64) = self.protected_with_generation(Operation::Me).await?;
        self.remember_user(generation, user.into()).await
    }

    async fn create_radar(&self, input: RadarCreateInput) -> Result<RadarView, BridgeError> {
        let body = input.payload()?;
        let (radar, _): (RadarResponse, u64) = self.protected_with_body_and_generation(Operation::RadarCreate, Some(body)).await?;
        Ok(radar.into())
    }

    async fn refresh_session(&self) -> Result<SessionView, BridgeError> {
        let (generation, access) = {
            let session = self.session.lock().await;
            (session.generation, session.access_token.clone())
        };
        self.refresh_locked(generation, access.as_deref()).await?;
        Ok(self.session.lock().await.view())
    }

    async fn logout(&self) -> Result<(), BridgeError> {
        let refresh = {
            let mut session = self.session.lock().await;
            let refresh = session.refresh_token.take();
            session.clear_and_fence();
            refresh
        };
        let Some(refresh) = refresh else { return Ok(()); };
        let payload = serde_json::to_vec(&json!({ "refresh_token": refresh })).map_err(|_| BridgeError::local("invalid_input", "Logout request could not be encoded"))?;
        let response = self.send(Operation::Logout, Some(payload), None).await?;
        if response.status.is_success() { Ok(()) } else { Err(remote_error(response)) }
    }
}

#[derive(Deserialize)]
struct ErrorEnvelope {
    error: ErrorDetail,
}

#[derive(Deserialize)]
struct ErrorDetail {
    code: String,
    message: String,
    request_id: String,
}

fn remote_error(response: HttpResponse) -> BridgeError {
    let status = response.status.as_u16();
    if let Ok(envelope) = serde_json::from_slice::<ErrorEnvelope>(&response.body) {
        return BridgeError { kind: "api", message: envelope.error.message, status: Some(status), code: Some(envelope.error.code), request_id: Some(envelope.error.request_id) };
    }
    BridgeError { kind: "http", message: "Backend request failed".into(), status: Some(status), code: None, request_id: None }
}

fn validate_origin(origin: &str) -> Result<Url, BridgeError> {
    let mut url = Url::parse(origin).map_err(|_| BridgeError::local("origin_denied", "API origin is invalid"))?;
    if url.scheme() != "http" || !url.username().is_empty() || url.password().is_some() || url.query().is_some() || url.fragment().is_some() || url.port().is_none() {
        return Err(BridgeError::local("origin_denied", "API origin must be an explicit local HTTP origin"));
    }
    let host = url.host_str().ok_or_else(|| BridgeError::local("origin_denied", "API origin has no host"))?;
    let localhost = host.eq_ignore_ascii_case("localhost");
    let ip_host = host.strip_prefix('[').and_then(|value| value.strip_suffix(']')).unwrap_or(host);
    let loopback = localhost || ip_host.parse::<IpAddr>().is_ok_and(|ip| ip.is_loopback());
    if !loopback || !matches!(url.path(), "/api/v1" | "/api/v1/") {
        return Err(BridgeError::local("origin_denied", "API origin must target loopback /api/v1"));
    }
    if localhost {
        url.set_host(Some("127.0.0.1")).map_err(|_| BridgeError::local("origin_denied", "Localhost could not be normalized"))?;
    }
    url.set_path("/api/v1/");
    Ok(url)
}

pub struct Bridge {
    client: Option<ApiClient>,
    setup_error: Option<BridgeError>,
}

impl Bridge {
    pub fn from_environment() -> Self {
        let configured = env::var("FLOWTRACER_API_ORIGIN").unwrap_or_else(|_| DEFAULT_ORIGIN.to_string());
        match ApiClient::new(&configured) {
            Ok(client) => Self { client: Some(client), setup_error: None },
            Err(error) => Self { client: None, setup_error: Some(error) },
        }
    }

    fn client(&self) -> Result<&ApiClient, BridgeError> {
        self.client.as_ref().ok_or_else(|| self.setup_error.clone().unwrap_or_else(|| BridgeError::local("bridge_unavailable", "Desktop bridge is unavailable")))
    }
}

#[tauri::command]
pub async fn bridge_status(bridge: State<'_, Bridge>) -> Result<BridgeStatus, BridgeError> {
    Ok(BridgeStatus { available: bridge.client.is_some(), origin: bridge.client.as_ref().map(ApiClient::safe_origin), error: bridge.setup_error.clone() })
}

#[tauri::command]
pub async fn health_ready(bridge: State<'_, Bridge>) -> Result<ReadinessView, BridgeError> {
    let response = bridge.client()?.send(Operation::Ready, None, None).await?;
    let ready: ReadinessResponse = bridge.client()?.require_success(response)?;
    Ok(ReadinessView { ready: ready.status == "ready" })
}

#[tauri::command]
pub async fn auth_register(bridge: State<'_, Bridge>, input: RegisterInput) -> Result<SessionView, BridgeError> {
    bridge.client()?.authenticate(Operation::Register, input.email, input.password, Some(input.display_name)).await
}

#[tauri::command]
pub async fn auth_login(bridge: State<'_, Bridge>, input: LoginInput) -> Result<SessionView, BridgeError> {
    bridge.client()?.authenticate(Operation::Login, input.email, input.password, None).await
}

#[tauri::command]
pub async fn auth_logout(bridge: State<'_, Bridge>) -> Result<(), BridgeError> {
    bridge.client()?.logout().await
}

#[tauri::command]
pub async fn auth_refresh(bridge: State<'_, Bridge>) -> Result<SessionView, BridgeError> {
    bridge.client()?.refresh_session().await
}

#[tauri::command]
pub async fn users_me(bridge: State<'_, Bridge>) -> Result<UserView, BridgeError> {
    bridge.client()?.current_user().await
}

#[tauri::command]
pub async fn radars_list(bridge: State<'_, Bridge>) -> Result<RadarPageView, BridgeError> {
    let page: RadarPage = bridge.client()?.protected(Operation::Radars).await?;
    Ok(RadarPageView { items: page.items.into_iter().map(Into::into).collect(), page: page.page, page_size: page.page_size, total: page.total })
}

#[tauri::command]
pub async fn radars_create(bridge: State<'_, Bridge>, input: RadarCreateInput) -> Result<RadarView, BridgeError> {
    bridge.client()?.create_radar(input).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::HashMap, sync::atomic::{AtomicBool, AtomicUsize, Ordering}};
    use tokio::{io::{AsyncReadExt, AsyncWriteExt}, net::TcpListener, task::JoinHandle, time::sleep};

    #[derive(Clone)]
    struct Request { method: String, path: String, body: String, authorization: Option<String> }
    struct Response { status: u16, body: String, headers: Vec<(String, String)>, delay_ms: u64 }

    async fn fake_server(handler: Arc<dyn Fn(Request) -> Response + Send + Sync>) -> (String, JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let task = tokio::spawn(async move {
            loop {
                let Ok((mut stream, _)) = listener.accept().await else { break };
                let handler = handler.clone();
                tokio::spawn(async move {
                    let mut data = Vec::new();
                    let mut buffer = [0u8; 2048];
                    loop {
                        let count = stream.read(&mut buffer).await.unwrap_or(0);
                        if count == 0 { break; }
                        data.extend_from_slice(&buffer[..count]);
                        if let Some(end) = data.windows(4).position(|part| part == b"\r\n\r\n") {
                            let headers = String::from_utf8_lossy(&data[..end + 4]);
                            let length = headers.lines().find_map(|line| line.to_ascii_lowercase().strip_prefix("content-length:").and_then(|value| value.trim().parse::<usize>().ok())).unwrap_or(0);
                            if data.len() >= end + 4 + length { break; }
                        }
                    }
                    let text = String::from_utf8_lossy(&data);
                    let method = text.lines().next().and_then(|line| line.split_whitespace().next()).unwrap_or("").to_string();
                    let path = text.lines().next().and_then(|line| line.split_whitespace().nth(1)).unwrap_or("/").to_string();
                    let body = text.split_once("\r\n\r\n").map(|(_, body)| body.to_string()).unwrap_or_default();
                    let headers: HashMap<_, _> = text.lines().skip(1).take_while(|line| !line.is_empty()).filter_map(|line| line.split_once(':')).map(|(key, value)| (key.to_ascii_lowercase(), value.trim().to_string())).collect();
                    let response = handler(Request { method, path, body, authorization: headers.get("authorization").cloned() });
                    if response.delay_ms > 0 { sleep(Duration::from_millis(response.delay_ms)).await; }
                    let reason = match response.status { 200 => "OK", 201 => "Created", 204 => "No Content", 302 => "Found", 401 => "Unauthorized", _ => "Error" };
                    let mut extra = String::new();
                    for (key, value) in response.headers { extra.push_str(&format!("{key}: {value}\r\n")); }
                    let wire = format!("HTTP/1.1 {} {}\r\nContent-Length: {}\r\nContent-Type: application/json\r\nConnection: close\r\n{}\r\n{}", response.status, reason, response.body.len(), extra, response.body);
                    let _ = stream.write_all(wire.as_bytes()).await;
                });
            }
        });
        (format!("http://{address}/api/v1"), task)
    }

    fn json_response(status: u16, body: Value) -> Response {
        Response { status, body: body.to_string(), headers: vec![], delay_ms: 0 }
    }

    fn user() -> Value {
        json!({"id":"00000000-0000-4000-8000-000000000001","email":"a@example.com","display_name":"A","profile":{},"is_active":true,"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"})
    }

    fn auth(access: &str, refresh: &str) -> Value {
        json!({"user":user(),"tokens":{"access_token":access,"refresh_token":refresh,"token_type":"bearer","expires_in":900}})
    }

    #[test]
    fn denies_non_loopback_and_ambiguous_origins() {
        for value in ["https://example.com/api/v1", "http://0.0.0.0:8000/api/v1", "http://127.0.0.1/api/v1", "http://127.0.0.1:8000/other", "http://user@127.0.0.1:8000/api/v1"] {
            assert!(validate_origin(value).is_err(), "accepted {value}");
        }
        assert!(validate_origin("http://localhost:8000/api/v1").is_ok());
        assert!(validate_origin("http://[::1]:8000/api/v1").is_ok());
    }

    #[tokio::test]
    async fn denies_redirects_and_oversized_responses() {
        let (origin, task) = fake_server(Arc::new(|request| {
            if request.path.contains("health/ready") {
                Response { status: 302, body: String::new(), headers: vec![("Location".into(), "https://example.com/".into())], delay_ms: 0 }
            } else { json_response(200, json!({})) }
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        let error = client.send(Operation::Ready, None, None).await.err().unwrap();
        assert_eq!(error.kind, "redirect_denied");
        task.abort();

        let huge = "x".repeat(RESPONSE_LIMIT + 1);
        let (origin, task) = fake_server(Arc::new(move |_| Response { status: 200, body: huge.clone(), headers: vec![], delay_ms: 0 })).await;
        let client = ApiClient::new(&origin).unwrap();
        let error = client.send(Operation::Ready, None, None).await.err().unwrap();
        assert_eq!(error.kind, "response_too_large");
        let error = client.send(Operation::Login, Some(vec![b'x'; REQUEST_LIMIT + 1]), None).await.err().unwrap();
        assert_eq!(error.kind, "request_too_large");
        task.abort();
    }

    #[tokio::test]
    async fn preserves_safe_error_code_status_and_request_id() {
        let calls = Arc::new(AtomicUsize::new(0));
        let count = calls.clone();
        let (origin, task) = fake_server(Arc::new(move |_| {
            let status = if count.fetch_add(1, Ordering::SeqCst) == 0 { 429 } else { 503 };
            json_response(status, json!({"error":{"code":if status == 429 {"ai_rate_limited"} else {"service_not_ready"},"message":"Try later","details":{},"request_id":"00000000-0000-4000-8000-000000000077"}}))
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        for status in [429, 503] {
            let response = client.send(Operation::Ready, None, None).await.unwrap();
            let error = client.require_success::<ReadinessResponse>(response).err().unwrap();
            assert_eq!(error.status, Some(status));
            assert_eq!(error.request_id.as_deref(), Some("00000000-0000-4000-8000-000000000077"));
            assert!(error.code.is_some());
        }
        task.abort();
    }

    #[tokio::test]
    async fn concurrent_401_uses_one_rotating_refresh() {
        let refreshes = Arc::new(AtomicUsize::new(0));
        let seen = refreshes.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("old", "refresh-1")),
            "/api/v1/auth/refresh" => { seen.fetch_add(1, Ordering::SeqCst); json_response(200, json!({"tokens":{"access_token":"new","refresh_token":"refresh-2","token_type":"bearer","expires_in":900}})) },
            "/api/v1/users/me" if request.authorization.as_deref() == Some("Bearer new") => json_response(200, user()),
            "/api/v1/users/me" => json_response(401, json!({"error":{"code":"invalid_access_token","message":"Invalid","details":{},"request_id":"00000000-0000-4000-8000-000000000099"}})),
            _ => json_response(404, json!({})),
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let (left, right) = tokio::join!(client.protected::<UserResponse>(Operation::Me), client.protected::<UserResponse>(Operation::Me));
        assert!(left.is_ok() && right.is_ok());
        assert_eq!(refreshes.load(Ordering::SeqCst), 1);
        task.abort();
    }

    #[tokio::test]
    async fn logout_fences_in_flight_user_data() {
        let me_started = Arc::new(AtomicBool::new(false));
        let flag = me_started.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("access", "refresh")),
            "/api/v1/auth/logout" => Response { status: 204, body: String::new(), headers: vec![], delay_ms: 0 },
            "/api/v1/users/me" => { flag.store(true, Ordering::SeqCst); Response { status: 200, body: user().to_string(), headers: vec![], delay_ms: 120 } },
            _ => json_response(404, json!({})),
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let pending = tokio::spawn({ let client = client.clone(); async move { client.protected::<UserResponse>(Operation::Me).await } });
        while !me_started.load(Ordering::SeqCst) { sleep(Duration::from_millis(5)).await; }
        client.logout().await.unwrap();
        let error = pending.await.unwrap().err().unwrap();
        assert_eq!(error.kind, "stale_session");
        task.abort();
    }

    #[tokio::test]
    async fn account_switch_fences_user_writeback() {
        let logins = Arc::new(AtomicUsize::new(0));
        let login_count = logins.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => {
                let second = login_count.fetch_add(1, Ordering::SeqCst) == 1;
                let mut response = auth(if second { "access-b" } else { "access-a" }, if second { "refresh-b" } else { "refresh-a" });
                if second {
                    response["user"]["id"] = json!("00000000-0000-4000-8000-000000000002");
                    response["user"]["email"] = json!("b@example.com");
                    response["user"]["display_name"] = json!("B");
                }
                json_response(200, response)
            }
            "/api/v1/users/me" => json_response(200, user()),
            _ => json_response(404, json!({})),
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let ordinary = client.current_user().await.unwrap();
        assert_eq!(ordinary.email, "a@example.com");

        let (fetched_tx, fetched_rx) = tokio::sync::oneshot::channel();
        let (resume_tx, resume_rx) = tokio::sync::oneshot::channel();
        let pending = tokio::spawn({
            let client = client.clone();
            async move {
                let (old_user, generation): (UserResponse, u64) = client.protected_with_generation(Operation::Me).await.unwrap();
                fetched_tx.send(()).unwrap();
                resume_rx.await.unwrap();
                client.remember_user(generation, old_user.into()).await
            }
        });
        fetched_rx.await.unwrap();
        let new_session = client.authenticate(Operation::Login, "b@example.com".into(), "long-password".into(), None).await.unwrap();
        assert_eq!(new_session.user.as_ref().unwrap().email, "b@example.com");
        resume_tx.send(()).unwrap();
        let error = pending.await.unwrap().err().unwrap();
        assert_eq!(error.kind, "stale_session");
        let session = client.session.lock().await;
        assert_eq!(session.user.as_ref().unwrap().email, "b@example.com");
        task.abort();
    }

    #[tokio::test]
    async fn fixture_covers_ready_register_login_user_radars_and_logout() {
        use std::sync::Mutex as StdMutex;
        let seen = Arc::new(StdMutex::new(Vec::<String>::new()));
        let calls = seen.clone();
        let (origin, task) = fake_server(Arc::new(move |request| {
            calls.lock().unwrap().push(request.path.clone());
            match request.path.as_str() {
                "/api/v1/health/ready" => json_response(200, json!({"status":"ready","checks":{"database":"ok","redis":"ok"}})),
                "/api/v1/auth/register" => json_response(201, auth("registered-access", "registered-refresh")),
                "/api/v1/auth/login" => json_response(200, auth("login-access", "login-refresh")),
                "/api/v1/auth/logout" => Response { status: 204, body: String::new(), headers: vec![], delay_ms: 0 },
                "/api/v1/users/me" => json_response(200, user()),
                path if path.starts_with("/api/v1/radars?") => json_response(200, json!({"items":[{"id":"00000000-0000-4000-8000-000000000010","name":"Tech","description":null,"goal":"Track tech","radar_type":"technology","categories":[],"keywords":[],"status":"active","notification_threshold":75,"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}],"page":1,"page_size":100,"total":1})),
                _ => json_response(404, json!({})),
            }
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        let ready: ReadinessResponse = client.require_success(client.send(Operation::Ready, None, None).await.unwrap()).unwrap();
        assert_eq!(ready.status, "ready");
        client.authenticate(Operation::Register, "a@example.com".into(), "long-password".into(), Some("A".into())).await.unwrap();
        client.logout().await.unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let _: UserResponse = client.protected(Operation::Me).await.unwrap();
        let page: RadarPage = client.protected(Operation::Radars).await.unwrap();
        assert_eq!(page.items.len(), 1);
        client.logout().await.unwrap();
        let paths = seen.lock().unwrap();
        for expected in ["/api/v1/health/ready", "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/users/me", "/api/v1/auth/logout"] {
            assert!(paths.iter().any(|path| path == expected), "missing {expected}");
        }
        assert!(paths.iter().any(|path| path.starts_with("/api/v1/radars?")));
        task.abort();
    }

    fn radar_input() -> RadarCreateInput {
        RadarCreateInput { name: " New Radar ".into(), goal: " Track change ".into(), radar_type: RadarType::Technology, description: None }
    }

    fn created_radar() -> Value {
        json!({"id":"00000000-0000-4000-8000-000000000011","name":"New Radar","description":null,"goal":"Track change","radar_type":"technology","categories":[],"keywords":[],"status":"active","notification_threshold":75,"created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"})
    }

    #[tokio::test]
    async fn create_radar_uses_typed_post_body_and_single_refresh() {
        let refreshes = Arc::new(AtomicUsize::new(0));
        let seen = refreshes.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("old", "refresh-1")),
            "/api/v1/auth/refresh" => { seen.fetch_add(1, Ordering::SeqCst); json_response(200, json!({"tokens":{"access_token":"new","refresh_token":"refresh-2"}})) },
            "/api/v1/radars" => {
                assert_eq!(request.method, "POST");
                assert_eq!(serde_json::from_str::<Value>(&request.body).unwrap(), json!({"name":"New Radar","goal":"Track change","radar_type":"technology","description":null}));
                if request.authorization.as_deref() == Some("Bearer new") { json_response(201, created_radar()) }
                else { json_response(401, json!({"error":{"code":"invalid_access_token","message":"Invalid","request_id":"00000000-0000-4000-8000-000000000099"}})) }
            }
            _ => json_response(404, json!({})),
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let radar = client.create_radar(radar_input()).await.unwrap();
        assert_eq!(radar.id, "00000000-0000-4000-8000-000000000011");
        assert_eq!(refreshes.load(Ordering::SeqCst), 1);
        task.abort();
    }

    #[tokio::test]
    async fn logout_fences_in_flight_created_radar() {
        let started = Arc::new(AtomicBool::new(false));
        let flag = started.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("access", "refresh")),
            "/api/v1/auth/logout" => Response { status: 204, body: String::new(), headers: vec![], delay_ms: 0 },
            "/api/v1/radars" => { flag.store(true, Ordering::SeqCst); Response { status: 201, body: created_radar().to_string(), headers: vec![], delay_ms: 120 } },
            _ => json_response(404, json!({})),
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let pending = tokio::spawn({ let client = client.clone(); async move { client.create_radar(radar_input()).await } });
        while !started.load(Ordering::SeqCst) { sleep(Duration::from_millis(5)).await; }
        client.logout().await.unwrap();
        assert_eq!(pending.await.unwrap().err().unwrap().kind, "stale_session");
        task.abort();
    }
}
