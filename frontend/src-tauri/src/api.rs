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

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
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

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum SourceType { Rss, Url, Api }

#[derive(Clone, Deserialize)]
struct SourceResponse {
    id: String,
    name: String,
    source_type: SourceType,
    url: String,
    normalized_url: String,
    poll_interval_minutes: i64,
    status: ResourceStatus,
}

#[derive(Deserialize)]
struct SourcePage { items: Vec<SourceResponse>, page: i64, page_size: i64, total: i64 }

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct SourceCreateInput { name: String, source_type: SourceType, url: String, poll_interval_minutes: i64 }

impl SourceCreateInput {
    fn payload(mut self) -> Result<Vec<u8>, BridgeError> {
        self.name = self.name.trim().to_string(); self.url = self.url.trim().to_string();
        if !(1..=160).contains(&self.name.chars().count()) || self.url.is_empty() || self.url.len() > 2048 || !(15..=10080).contains(&self.poll_interval_minutes) || self.source_type == SourceType::Api {
            return Err(BridgeError::local("invalid_input", "Source create input is outside the frozen contract"));
        }
        let parsed = Url::parse(&self.url).map_err(|_| BridgeError::local("invalid_input", "Source URL is invalid"))?;
        if !matches!(parsed.scheme(), "http" | "https") || !parsed.username().is_empty() || parsed.password().is_some() {
            return Err(BridgeError::local("invalid_input", "Source URL must be HTTP(S) without embedded credentials"));
        }
        serde_json::to_vec(&json!({"name":self.name,"source_type":self.source_type,"url":self.url,"poll_interval_minutes":self.poll_interval_minutes}))
            .map_err(|_| BridgeError::local("invalid_input", "Source request could not be encoded"))
    }
}

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SourceView { id: String, name: String, source_type: SourceType, url: String, normalized_url: String, poll_interval_minutes: i64, status: ResourceStatus }
impl From<SourceResponse> for SourceView { fn from(value: SourceResponse) -> Self { Self { id:value.id,name:value.name,source_type:value.source_type,url:value.url,normalized_url:value.normalized_url,poll_interval_minutes:value.poll_interval_minutes,status:value.status } } }

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SourcePageView { items: Vec<SourceView>, page: i64, page_size: i64, total: i64 }

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum CollectionRunStatus { Queued, Running, Succeeded, Partial, Failed }

#[derive(Deserialize)]
struct CollectionQueuedResponse { run_id: String, status: CollectionRunStatus }

#[derive(Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CollectionRunView { id: String, source_id: String, status: CollectionRunStatus, fetched_count: i64, created_count: i64, duplicate_count: i64, failed_count: i64, error_code: Option<String>, error_message: Option<String> }

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CollectionQueuedView { run_id: String, status: CollectionRunStatus }

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum AnalysisStatus { Pending, Running, Completed, Failed }

#[derive(Clone, Copy, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum Recommendation { MustRead, Read, Monitor, Archive }

#[derive(Clone, Deserialize)]
#[serde(untagged)]
enum DecimalValue { String(String), Number(f64) }
impl DecimalValue {
    fn finite_score(self) -> Result<f64, BridgeError> {
        let value=match self { Self::String(value)=>value.parse::<f64>().map_err(|_|BridgeError::local("invalid_response","Backend returned an invalid intelligence score"))?,Self::Number(value)=>value };
        if !value.is_finite()||!(0.0..=100.0).contains(&value){return Err(BridgeError::local("invalid_response","Backend returned an invalid intelligence score"));} Ok(value)
    }
}

#[derive(Clone, Deserialize)]
struct IntelligenceResponse { id:String,document_id:String,radar_id:String,title:String,canonical_url:String,summary:Option<String>,category:Option<String>,relevance:Option<i64>,importance:Option<i64>,novelty:Option<i64>,impact:Option<i64>,radar_score:Option<DecimalValue>,recommendation:Option<Recommendation>,reason:Option<String>,status:AnalysisStatus,error_code:Option<String>,error_message:Option<String>,pipeline_version:String,prompt_version:String,provider:Option<String>,model:Option<String>,bookmarked:bool,created_at:String,updated_at:String }
#[derive(Deserialize)] struct IntelligencePageResponse { items:Vec<IntelligenceResponse>,page:i64,page_size:i64,total:i64 }
#[derive(Deserialize)] struct IntelligenceDetailResponse { #[serde(flatten)] item:IntelligenceResponse,content:String,author:Option<String>,language:Option<String>,word_count:i64 }

#[derive(Clone, Deserialize)]
#[serde(rename_all="camelCase",deny_unknown_fields)]
pub struct IntelligenceQuery { page:i64,page_size:i64,radar_id:Option<String>,status:Option<AnalysisStatus>,recommendation:Option<Recommendation>,category:Option<String>,min_score:Option<f64> }

#[derive(Clone, Serialize)]
#[serde(rename_all="camelCase")]
pub struct IntelligenceView { id:String,document_id:String,radar_id:String,title:String,canonical_url:String,summary:Option<String>,category:Option<String>,relevance:Option<i64>,importance:Option<i64>,novelty:Option<i64>,impact:Option<i64>,radar_score:Option<f64>,recommendation:Option<Recommendation>,reason:Option<String>,status:AnalysisStatus,error_code:Option<String>,error_message:Option<String>,pipeline_version:String,prompt_version:String,provider:Option<String>,model:Option<String>,bookmarked:bool,created_at:String,updated_at:String }
#[derive(Serialize)] #[serde(rename_all="camelCase")] pub struct IntelligencePageView { items:Vec<IntelligenceView>,page:i64,page_size:i64,total:i64 }
#[derive(Serialize)] #[serde(rename_all="camelCase")] pub struct IntelligenceDetailView { #[serde(flatten)] item:IntelligenceView,content:String,author:Option<String>,language:Option<String>,word_count:i64 }

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RadarCreateInput {
    name: String,
    goal: String,
    radar_type: RadarType,
    description: Option<String>,
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct RadarUpdateInput {
    name: String,
    goal: String,
    radar_type: RadarType,
    description: Option<String>,
    notification_threshold: i64,
}

impl RadarUpdateInput {
    fn payload(mut self) -> Result<Vec<u8>, BridgeError> {
        self.name = self.name.trim().to_string();
        self.goal = self.goal.trim().to_string();
        if !(1..=120).contains(&self.name.chars().count()) || !(1..=4000).contains(&self.goal.chars().count()) || !(0..=100).contains(&self.notification_threshold) {
            return Err(BridgeError::local("invalid_input", "Radar update is outside the allowed range"));
        }
        self.description = self.description.and_then(|value| { let value = value.trim().to_string(); if value.is_empty() { None } else { Some(value) } });
        serde_json::to_vec(&json!({"name":self.name,"goal":self.goal,"radar_type":self.radar_type,"description":self.description,"notification_threshold":self.notification_threshold}))
            .map_err(|_| BridgeError::local("invalid_input", "Radar update could not be encoded"))
    }
}

fn canonical_radar_id(value: &str) -> Result<String, BridgeError> {
    let bytes = value.as_bytes();
    let valid = bytes.len() == 36 && bytes.iter().enumerate().all(|(index, byte)| {
        if matches!(index, 8 | 13 | 18 | 23) { *byte == b'-' } else { byte.is_ascii_digit() || matches!(byte, b'a'..=b'f') }
    });
    if valid { Ok(value.to_string()) } else { Err(BridgeError::local("invalid_input", "Radar identity must be a canonical UUID")) }
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

#[derive(Clone)]
enum Operation {
    Register,
    Login,
    Refresh,
    Logout,
    Me,
    Ready,
    Radars,
    RadarCreate,
    RadarDetail(String),
    RadarUpdate(String),
    RadarPause(String),
    RadarResume(String),
    RadarDelete(String),
    Sources(i64, i64),
    SourceCreate,
    RadarSources(String, i64, i64),
    SourceBind(String, String),
    SourceUnbind(String, String),
    SourceCollect(String, String),
    CollectionRun(String),
    IntelligenceList(String),
    IntelligenceDetail(String),
}

impl Operation {
    fn method(&self) -> Method {
        match self {
            Self::Register | Self::Login | Self::Refresh | Self::Logout | Self::RadarCreate | Self::RadarPause(_) | Self::RadarResume(_) | Self::SourceCreate | Self::SourceBind(_, _) | Self::SourceCollect(_, _) => Method::POST,
            Self::RadarUpdate(_) => Method::PATCH,
            Self::RadarDelete(_) | Self::SourceUnbind(_, _) => Method::DELETE,
            Self::Me | Self::Ready | Self::Radars | Self::RadarDetail(_) | Self::Sources(_, _) | Self::RadarSources(_, _, _) | Self::CollectionRun(_) | Self::IntelligenceList(_) | Self::IntelligenceDetail(_) => Method::GET,
        }
    }

    fn path(&self) -> String {
        match self {
            Self::Register => "auth/register".into(), Self::Login => "auth/login".into(), Self::Refresh => "auth/refresh".into(),
            Self::Logout => "auth/logout".into(), Self::Me => "users/me".into(), Self::Ready => "health/ready".into(),
            Self::Radars => "radars?page=1&page_size=100".into(), Self::RadarCreate => "radars".into(),
            Self::RadarDetail(id) | Self::RadarUpdate(id) | Self::RadarDelete(id) => format!("radars/{id}"),
            Self::RadarPause(id) => format!("radars/{id}/pause"),
            Self::RadarResume(id) => format!("radars/{id}/resume"),
            Self::Sources(page,size) => format!("sources?page={page}&page_size={size}"), Self::SourceCreate => "sources".into(),
            Self::RadarSources(id,page,size) => format!("radars/{id}/sources?page={page}&page_size={size}"),
            Self::SourceBind(radar, source) | Self::SourceUnbind(radar, source) => format!("radars/{radar}/sources/{source}"),
            Self::SourceCollect(source, _) => format!("sources/{source}/collect"), Self::CollectionRun(run) => format!("collection-runs/{run}"),
            Self::IntelligenceList(query) => format!("intelligence?{query}"), Self::IntelligenceDetail(id) => format!("intelligence/{id}"),
        }
    }
}

struct HttpResponse {
    status: StatusCode,
    body: Vec<u8>,
    location: Option<String>,
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
        let url = self.base.join(&operation.path()).map_err(|_| BridgeError::local("path_denied", "Operation path is not permitted"))?;
        if url.scheme() != self.base.scheme() || url.host_str() != self.base.host_str() || url.port_or_known_default() != self.base.port_or_known_default() {
            return Err(BridgeError::local("origin_denied", "Operation left the configured API origin"));
        }
        let mut request = self.http.request(operation.method(), url).header(header::ACCEPT, "application/json");
        if let Operation::SourceCollect(_, key) = &operation { request = request.header("Idempotency-Key", key); }
        if let Some(token) = access_token {
            request = request.bearer_auth(token);
        }
        if let Some(payload) = body {
            request = request.header(header::CONTENT_TYPE, "application/json").body(payload);
        }
        let mut response = request.send().await.map_err(|_| BridgeError::local("network", "Desktop bridge request failed"))?;
        let status = response.status();
        let location = response.headers().get(header::LOCATION).and_then(|value| value.to_str().ok()).map(str::to_string);
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
        Ok(HttpResponse { status, body: bytes, location })
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
        let first = self.send(operation.clone(), body.clone(), Some(&access)).await?;
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

    async fn protected_json_status_with_body<T: DeserializeOwned>(&self, operation: Operation, expected: StatusCode, body: Option<Vec<u8>>) -> Result<T, BridgeError> {
        let (generation, access) = {
            let session = self.session.lock().await;
            (session.generation, session.access_token.clone().ok_or_else(|| BridgeError::local("authentication_required", "Sign in is required"))?)
        };
        let first = self.send(operation.clone(), body.clone(), Some(&access)).await?;
        let response = if first.status == StatusCode::UNAUTHORIZED {
            let refreshed = self.refresh_locked(generation, Some(&access)).await?;
            self.send(operation, body, Some(&refreshed)).await?
        } else { first };
        if response.status != expected {
            if !response.status.is_success() { return Err(remote_error(response)); }
            return Err(BridgeError { kind: "invalid_response", message: "Backend returned an unexpected success status".into(), status: Some(response.status.as_u16()), code: None, request_id: None });
        }
        let result = serde_json::from_slice(&response.body).map_err(|_| BridgeError { kind: "invalid_response", message: "Backend returned an invalid response".into(), status: Some(response.status.as_u16()), code: None, request_id: None })?;
        let session = self.session.lock().await;
        if session.generation != generation { return Err(BridgeError::local("stale_session", "Session changed while request was in flight")); }
        Ok(result)
    }

    async fn protected_json_status<T: DeserializeOwned>(&self, operation: Operation, expected: StatusCode) -> Result<T, BridgeError> {
        self.protected_json_status_with_body(operation, expected, None).await
    }

    async fn protected_no_content(&self, operation: Operation) -> Result<(), BridgeError> {
        let (generation, access) = {
            let session = self.session.lock().await;
            (session.generation, session.access_token.clone().ok_or_else(|| BridgeError::local("authentication_required", "Sign in is required"))?)
        };
        let first = self.send(operation.clone(), None, Some(&access)).await?;
        let response = if first.status == StatusCode::UNAUTHORIZED {
            let refreshed = self.refresh_locked(generation, Some(&access)).await?;
            self.send(operation, None, Some(&refreshed)).await?
        } else { first };
        if response.status != StatusCode::NO_CONTENT || !response.body.is_empty() {
            if !response.status.is_success() { return Err(remote_error(response)); }
            return Err(BridgeError { kind: "invalid_response", message: "Backend returned an invalid no-content response".into(), status: Some(response.status.as_u16()), code: None, request_id: None });
        }
        let session = self.session.lock().await;
        if session.generation != generation { return Err(BridgeError::local("stale_session", "Session changed while request was in flight")); }
        Ok(())
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

    async fn radar_detail(&self, radar_id: String) -> Result<RadarView, BridgeError> {
        let id = canonical_radar_id(&radar_id)?;
        let radar: RadarResponse = self.protected(Operation::RadarDetail(id.clone())).await?;
        if radar.id != id { return Err(BridgeError::local("invalid_response", "Backend returned a different Radar identity")); }
        Ok(radar.into())
    }

    async fn update_radar(&self, radar_id: String, input: RadarUpdateInput) -> Result<RadarView, BridgeError> {
        let id = canonical_radar_id(&radar_id)?;
        let body = input.payload()?;
        let (radar, _): (RadarResponse, u64) = self.protected_with_body_and_generation(Operation::RadarUpdate(id.clone()), Some(body)).await?;
        if radar.id != id { return Err(BridgeError::local("invalid_response", "Backend returned a different Radar identity")); }
        Ok(radar.into())
    }

    async fn transition_radar(&self, radar_id: String, expected: ResourceStatus) -> Result<RadarView, BridgeError> {
        let id = canonical_radar_id(&radar_id)?;
        let operation = match expected { ResourceStatus::Paused => Operation::RadarPause(id.clone()), ResourceStatus::Active => Operation::RadarResume(id.clone()), ResourceStatus::Archived => return Err(BridgeError::local("invalid_input", "Archived is not a lifecycle transition target")) };
        let radar: RadarResponse = self.protected_json_status(operation, StatusCode::OK).await?;
        if radar.id != id || radar.status != expected { return Err(BridgeError::local("invalid_response", "Backend returned a mismatched Radar lifecycle response")); }
        Ok(radar.into())
    }

    async fn delete_radar(&self, radar_id: String) -> Result<(), BridgeError> {
        let id = canonical_radar_id(&radar_id)?;
        self.protected_no_content(Operation::RadarDelete(id)).await
    }

    fn pagination(page:i64,size:i64)->Result<(i64,i64),BridgeError>{if page<1||!(1..=100).contains(&size){Err(BridgeError::local("invalid_input","Source pagination is outside the frozen contract"))}else{Ok((page,size))}}
    fn source_page(&self, page: SourcePage, expected_page:i64, expected_size:i64) -> Result<SourcePageView, BridgeError> {
        if page.page != expected_page || page.page_size != expected_size || page.total < 0 || page.items.iter().any(|source| canonical_radar_id(&source.id).is_err()) {
            return Err(BridgeError::local("invalid_response", "Backend returned an invalid Source page"));
        }
        Ok(SourcePageView { items: page.items.into_iter().map(Into::into).collect(), page: page.page, page_size: page.page_size, total: page.total })
    }

    async fn list_sources(&self, page:i64, size:i64) -> Result<SourcePageView, BridgeError> {
        let (page_number,page_size)=Self::pagination(page,size)?; let value: SourcePage = self.protected_json_status(Operation::Sources(page_number,page_size), StatusCode::OK).await?; self.source_page(value,page_number,page_size)
    }

    async fn list_radar_sources(&self, radar_id: String, page:i64, size:i64) -> Result<SourcePageView, BridgeError> {
        let id=canonical_radar_id(&radar_id)?;let(page_number,page_size)=Self::pagination(page,size)?;let value:SourcePage=self.protected_json_status(Operation::RadarSources(id,page_number,page_size),StatusCode::OK).await?;self.source_page(value,page_number,page_size)
    }

    async fn create_source(&self, input: SourceCreateInput) -> Result<SourceView, BridgeError> {
        let body=input.payload()?; let source: SourceResponse=self.protected_json_status_with_body(Operation::SourceCreate,StatusCode::CREATED,Some(body)).await?;
        canonical_radar_id(&source.id)?; Ok(source.into())
    }

    async fn bind_source(&self, radar_id: String, source_id: String, bind: bool) -> Result<(), BridgeError> {
        let radar=canonical_radar_id(&radar_id)?; let source=canonical_radar_id(&source_id)?;
        self.protected_no_content(if bind { Operation::SourceBind(radar,source) } else { Operation::SourceUnbind(radar,source) }).await
    }

    async fn collect_source(&self, source_id: String, idempotency_key: String) -> Result<CollectionQueuedView, BridgeError> {
        let source=canonical_radar_id(&source_id)?; let key=canonical_radar_id(&idempotency_key)?;
        let operation=Operation::SourceCollect(source,key); let (generation,access)={let session=self.session.lock().await;(session.generation,session.access_token.clone().ok_or_else(||BridgeError::local("authentication_required","Sign in is required"))?)};
        let first=self.send(operation.clone(),None,Some(&access)).await?; let response=if first.status==StatusCode::UNAUTHORIZED {let refreshed=self.refresh_locked(generation,Some(&access)).await?;self.send(operation,None,Some(&refreshed)).await?}else{first};
        if response.status!=StatusCode::ACCEPTED { if !response.status.is_success(){return Err(remote_error(response));} return Err(BridgeError{kind:"invalid_response",message:"Backend returned an unexpected collect status".into(),status:Some(response.status.as_u16()),code:None,request_id:None}); }
        let queued:CollectionQueuedResponse=serde_json::from_slice(&response.body).map_err(|_|BridgeError::local("invalid_response","Backend returned an invalid queued collection"))?;
        let run=canonical_radar_id(&queued.run_id)?;
        let expected_relative=format!("/api/v1/collection-runs/{run}"); let expected_absolute=format!("{}{}",self.safe_origin(),expected_relative.trim_start_matches("/api/v1"));
        if response.location.as_deref()!=Some(expected_relative.as_str()) && response.location.as_deref()!=Some(expected_absolute.as_str()) {return Err(BridgeError::local("invalid_response","Collection Location is missing or unsafe"));}
        if self.session.lock().await.generation!=generation{return Err(BridgeError::local("stale_session","Session changed while request was in flight"));}
        Ok(CollectionQueuedView{run_id:run,status:queued.status})
    }

    async fn collection_run(&self, run_id: String, source_id: String) -> Result<CollectionRunView, BridgeError> {
        let run=canonical_radar_id(&run_id)?; let source=canonical_radar_id(&source_id)?; let value:CollectionRunView=self.protected_json_status(Operation::CollectionRun(run.clone()),StatusCode::OK).await?;
        if value.id!=run || value.source_id!=source {return Err(BridgeError::local("invalid_response","Backend returned a mismatched CollectionRun identity"));} Ok(value)
    }

    fn intelligence_item(value:IntelligenceResponse)->Result<IntelligenceView,BridgeError>{
        canonical_radar_id(&value.id)?;canonical_radar_id(&value.document_id)?;canonical_radar_id(&value.radar_id)?;
        for score in [value.relevance,value.importance,value.novelty,value.impact].into_iter().flatten(){if !(0..=100).contains(&score){return Err(BridgeError::local("invalid_response","Backend returned an invalid intelligence component score"));}}
        let radar_score=match value.radar_score{Some(score)=>Some(score.finite_score()?),None=>None};
        Ok(IntelligenceView{id:value.id,document_id:value.document_id,radar_id:value.radar_id,title:value.title,canonical_url:value.canonical_url,summary:value.summary,category:value.category,relevance:value.relevance,importance:value.importance,novelty:value.novelty,impact:value.impact,radar_score,recommendation:value.recommendation,reason:value.reason,status:value.status,error_code:value.error_code,error_message:value.error_message,pipeline_version:value.pipeline_version,prompt_version:value.prompt_version,provider:value.provider,model:value.model,bookmarked:value.bookmarked,created_at:value.created_at,updated_at:value.updated_at})
    }

    fn intelligence_path(query:IntelligenceQuery)->Result<(String,i64,i64),BridgeError>{
        let(page,size)=Self::pagination(query.page,query.page_size)?;let radar=match query.radar_id{Some(value)=>Some(canonical_radar_id(&value)?),None=>None};let category=query.category.map(|value|value.trim().to_string());
        if category.as_ref().is_some_and(|value|value.is_empty()||value.chars().count()>120)||query.min_score.is_some_and(|value|!value.is_finite()||!(0.0..=100.0).contains(&value)){return Err(BridgeError::local("invalid_input","Intelligence filters are outside the frozen contract"));}
        let mut url=Url::parse("http://localhost/intelligence").map_err(|_|BridgeError::local("client_setup","Intelligence query could not be built"))?;{let mut pairs=url.query_pairs_mut();pairs.append_pair("page",&page.to_string()).append_pair("page_size",&size.to_string());if let Some(value)=radar.as_deref(){pairs.append_pair("radar_id",value);}if let Some(value)=query.status{pairs.append_pair("status",match value{AnalysisStatus::Pending=>"pending",AnalysisStatus::Running=>"running",AnalysisStatus::Completed=>"completed",AnalysisStatus::Failed=>"failed"});}if let Some(value)=query.recommendation{pairs.append_pair("recommendation",match value{Recommendation::MustRead=>"must_read",Recommendation::Read=>"read",Recommendation::Monitor=>"monitor",Recommendation::Archive=>"archive"});}if let Some(value)=category.as_deref(){pairs.append_pair("category",value);}if let Some(value)=query.min_score{pairs.append_pair("min_score",&value.to_string());}}
        Ok((url.query().unwrap_or_default().to_string(),page,size))
    }

    async fn intelligence_list(&self,query:IntelligenceQuery)->Result<IntelligencePageView,BridgeError>{let(path,page,size)=Self::intelligence_path(query)?;let response:IntelligencePageResponse=self.protected_json_status(Operation::IntelligenceList(path),StatusCode::OK).await?;if response.page!=page||response.page_size!=size||response.total<0||response.items.len()>size as usize||response.items.len() as i64>response.total{return Err(BridgeError::local("invalid_response","Backend returned an invalid Intelligence page"));}let items=response.items.into_iter().map(Self::intelligence_item).collect::<Result<Vec<_>,_>>()?;Ok(IntelligencePageView{items,page:response.page,page_size:response.page_size,total:response.total})}
    async fn intelligence_detail(&self,analysis_id:String,radar_id:String)->Result<IntelligenceDetailView,BridgeError>{let id=canonical_radar_id(&analysis_id)?;let radar=canonical_radar_id(&radar_id)?;let response:IntelligenceDetailResponse=self.protected_json_status(Operation::IntelligenceDetail(id.clone()),StatusCode::OK).await?;if response.item.id!=id||response.item.radar_id!=radar||response.word_count<0{return Err(BridgeError::local("invalid_response","Backend returned a mismatched Intelligence detail"));}Ok(IntelligenceDetailView{item:Self::intelligence_item(response.item)?,content:response.content,author:response.author,language:response.language,word_count:response.word_count})}

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

#[tauri::command]
pub async fn radars_get(bridge: State<'_, Bridge>, radar_id: String) -> Result<RadarView, BridgeError> {
    bridge.client()?.radar_detail(radar_id).await
}

#[tauri::command]
pub async fn radars_update(bridge: State<'_, Bridge>, radar_id: String, input: RadarUpdateInput) -> Result<RadarView, BridgeError> {
    bridge.client()?.update_radar(radar_id, input).await
}

#[tauri::command]
pub async fn radars_pause(bridge: State<'_, Bridge>, radar_id: String) -> Result<RadarView, BridgeError> {
    bridge.client()?.transition_radar(radar_id, ResourceStatus::Paused).await
}

#[tauri::command]
pub async fn radars_resume(bridge: State<'_, Bridge>, radar_id: String) -> Result<RadarView, BridgeError> {
    bridge.client()?.transition_radar(radar_id, ResourceStatus::Active).await
}

#[tauri::command]
pub async fn radars_delete(bridge: State<'_, Bridge>, radar_id: String) -> Result<(), BridgeError> {
    bridge.client()?.delete_radar(radar_id).await
}

#[tauri::command]
pub async fn sources_list(bridge: State<'_, Bridge>, page: i64, page_size: i64) -> Result<SourcePageView, BridgeError> { bridge.client()?.list_sources(page,page_size).await }

#[tauri::command]
pub async fn radar_sources_list(bridge: State<'_, Bridge>, radar_id: String, page: i64, page_size: i64) -> Result<SourcePageView, BridgeError> { bridge.client()?.list_radar_sources(radar_id,page,page_size).await }

#[tauri::command]
pub async fn sources_create(bridge: State<'_, Bridge>, input: SourceCreateInput) -> Result<SourceView, BridgeError> { bridge.client()?.create_source(input).await }

#[tauri::command]
pub async fn radar_sources_bind(bridge: State<'_, Bridge>, radar_id: String, source_id: String) -> Result<(), BridgeError> { bridge.client()?.bind_source(radar_id,source_id,true).await }

#[tauri::command]
pub async fn radar_sources_unbind(bridge: State<'_, Bridge>, radar_id: String, source_id: String) -> Result<(), BridgeError> { bridge.client()?.bind_source(radar_id,source_id,false).await }

#[tauri::command]
pub async fn sources_collect(bridge: State<'_, Bridge>, source_id: String, idempotency_key: String) -> Result<CollectionQueuedView, BridgeError> { bridge.client()?.collect_source(source_id,idempotency_key).await }

#[tauri::command]
pub async fn collection_runs_get(bridge: State<'_, Bridge>, run_id: String, source_id: String) -> Result<CollectionRunView, BridgeError> { bridge.client()?.collection_run(run_id,source_id).await }

#[tauri::command]
pub async fn intelligence_list(bridge:State<'_,Bridge>,input:IntelligenceQuery)->Result<IntelligencePageView,BridgeError>{bridge.client()?.intelligence_list(input).await}

#[tauri::command]
pub async fn intelligence_get(bridge:State<'_,Bridge>,analysis_id:String,radar_id:String)->Result<IntelligenceDetailView,BridgeError>{bridge.client()?.intelligence_detail(analysis_id,radar_id).await}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{collections::HashMap, sync::atomic::{AtomicBool, AtomicUsize, Ordering}};
    use tokio::{io::{AsyncReadExt, AsyncWriteExt}, net::TcpListener, task::JoinHandle, time::sleep};

    #[derive(Clone)]
    struct Request { method: String, path: String, body: String, authorization: Option<String>, idempotency_key: Option<String> }
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
                    let response = handler(Request { method, path, body, authorization: headers.get("authorization").cloned(), idempotency_key: headers.get("idempotency-key").cloned() });
                    if response.delay_ms > 0 { sleep(Duration::from_millis(response.delay_ms)).await; }
                    let reason = match response.status { 200 => "OK", 201 => "Created", 202 => "Accepted", 204 => "No Content", 302 => "Found", 401 => "Unauthorized", _ => "Error" };
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

    fn radar_update_input() -> RadarUpdateInput {
        RadarUpdateInput { name: " Edited Radar ".into(), goal: " New goal ".into(), radar_type: RadarType::Market, description: Some(" ".into()), notification_threshold: 64 }
    }

    #[test]
    fn radar_identity_and_update_payload_are_strict() {
        let id = "00000000-0000-4000-8000-000000000011";
        assert_eq!(canonical_radar_id(id).unwrap(), id);
        for bad in ["../x", "00000000-0000-4000-8000-000000000011?x=1", "00000000-0000-4000-8000-000000000011%2f", "HTTP://EXAMPLE.COM", "00000000-0000-4000-8000-00000000001A"] { assert!(canonical_radar_id(bad).is_err()); }
        let payload: Value = serde_json::from_slice(&radar_update_input().payload().unwrap()).unwrap();
        assert_eq!(payload, json!({"name":"Edited Radar","goal":"New goal","radar_type":"market","description":null,"notification_threshold":64}));
        assert!(payload.get("categories").is_none() && payload.get("keywords").is_none() && payload.get("status").is_none());
    }

    #[tokio::test]
    async fn radar_detail_and_update_use_typed_path_refresh_and_body() {
        let id = "00000000-0000-4000-8000-000000000011";
        let refreshes = Arc::new(AtomicUsize::new(0)); let seen = refreshes.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("old", "refresh")),
            "/api/v1/auth/refresh" => { seen.fetch_add(1, Ordering::SeqCst); json_response(200, json!({"tokens":{"access_token":"new","refresh_token":"refresh-2"}})) },
            "/api/v1/radars/00000000-0000-4000-8000-000000000011" if request.authorization.as_deref() != Some("Bearer new") => json_response(401, json!({"error":{"code":"invalid_access_token","message":"Invalid","request_id":"00000000-0000-4000-8000-000000000099"}})),
            "/api/v1/radars/00000000-0000-4000-8000-000000000011" if request.method == "GET" => json_response(200, created_radar()),
            "/api/v1/radars/00000000-0000-4000-8000-000000000011" => { assert_eq!(request.method, "PATCH"); assert_eq!(serde_json::from_str::<Value>(&request.body).unwrap(), json!({"name":"Edited Radar","goal":"New goal","radar_type":"market","description":null,"notification_threshold":64})); let mut value=created_radar(); value["name"]=json!("Edited Radar"); value["goal"]=json!("New goal"); value["radar_type"]=json!("market"); value["notification_threshold"]=json!(64); json_response(200,value) },
            _ => json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap(); client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();
        assert_eq!(client.radar_detail(id.into()).await.unwrap().id,id); assert_eq!(client.update_radar(id.into(),radar_update_input()).await.unwrap().name,"Edited Radar"); assert_eq!(refreshes.load(Ordering::SeqCst),1); task.abort();
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

    #[tokio::test]
    async fn logout_fences_in_flight_updated_radar() {
        let started = Arc::new(AtomicBool::new(false));
        let flag = started.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("access", "refresh")),
            "/api/v1/auth/logout" => Response { status: 204, body: String::new(), headers: vec![], delay_ms: 0 },
            "/api/v1/radars/00000000-0000-4000-8000-000000000011" => { flag.store(true, Ordering::SeqCst); Response { status: 200, body: created_radar().to_string(), headers: vec![], delay_ms: 120 } },
            _ => json_response(404, json!({})),
        })).await;
        let client = ApiClient::new(&origin).unwrap();
        client.authenticate(Operation::Login, "a@example.com".into(), "long-password".into(), None).await.unwrap();
        let pending = tokio::spawn({ let client = client.clone(); async move { client.update_radar("00000000-0000-4000-8000-000000000011".into(), radar_update_input()).await } });
        while !started.load(Ordering::SeqCst) { sleep(Duration::from_millis(5)).await; }
        client.logout().await.unwrap();
        assert_eq!(pending.await.unwrap().err().unwrap().kind, "stale_session");
        task.abort();
    }

    #[tokio::test]
    async fn radar_lifecycle_uses_typed_paths_refresh_status_and_delete_204() {
        let refreshes = Arc::new(AtomicUsize::new(0)); let seen = refreshes.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("old", "refresh")),
            "/api/v1/auth/refresh" => { seen.fetch_add(1, Ordering::SeqCst); json_response(200, json!({"tokens":{"access_token":"new","refresh_token":"refresh-2"}})) },
            "/api/v1/radars/00000000-0000-4000-8000-000000000011/pause" if request.authorization.as_deref() != Some("Bearer new") => json_response(401, json!({"error":{"code":"invalid_access_token","message":"Invalid","request_id":"00000000-0000-4000-8000-000000000099"}})),
            "/api/v1/radars/00000000-0000-4000-8000-000000000011/pause" => { assert_eq!(request.method, "POST"); let mut value=created_radar(); value["status"]=json!("paused"); json_response(200,value) },
            "/api/v1/radars/00000000-0000-4000-8000-000000000011/resume" => { assert_eq!(request.method, "POST"); json_response(200,created_radar()) },
            "/api/v1/radars/00000000-0000-4000-8000-000000000011" => { assert_eq!(request.method, "DELETE"); Response { status: 204, body: String::new(), headers: vec![], delay_ms: 0 } },
            _ => json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap(); client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();
        assert_eq!(client.transition_radar("00000000-0000-4000-8000-000000000011".into(),ResourceStatus::Paused).await.unwrap().status,ResourceStatus::Paused);
        assert_eq!(client.transition_radar("00000000-0000-4000-8000-000000000011".into(),ResourceStatus::Active).await.unwrap().status,ResourceStatus::Active);
        client.delete_radar("00000000-0000-4000-8000-000000000011".into()).await.unwrap(); assert_eq!(refreshes.load(Ordering::SeqCst),1); task.abort();
    }

    #[tokio::test]
    async fn radar_lifecycle_rejects_malformed_identity_mismatched_status_and_non_204_delete() {
        let pauses=Arc::new(AtomicUsize::new(0)); let pause_count=pauses.clone();
        let (origin, task) = fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200, auth("access", "refresh")),
            path if path.ends_with("/pause") => { let call=pause_count.fetch_add(1,Ordering::SeqCst); if call==0 { json_response(200,created_radar()) } else { let mut value=created_radar(); value["status"]=json!("paused"); json_response(202,value) } },
            path if path.ends_with("000000000011") => Response { status: 202, body: String::new(), headers: vec![], delay_ms: 0 },
            _ => json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap(); client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();
        assert_eq!(client.transition_radar("../x".into(),ResourceStatus::Paused).await.err().unwrap().kind,"invalid_input");
        assert_eq!(client.delete_radar("00000000-0000-4000-8000-000000000011?x=1".into()).await.err().unwrap().kind,"invalid_input");
        assert_eq!(client.transition_radar("00000000-0000-4000-8000-000000000011".into(),ResourceStatus::Paused).await.err().unwrap().kind,"invalid_response");
        let transition=client.transition_radar("00000000-0000-4000-8000-000000000011".into(),ResourceStatus::Paused).await.err().unwrap(); assert_eq!(transition.kind,"invalid_response"); assert_eq!(transition.status,Some(202));
        let error=client.delete_radar("00000000-0000-4000-8000-000000000011".into()).await.err().unwrap(); assert_eq!(error.kind,"invalid_response"); assert_eq!(error.status,Some(202)); task.abort();
    }

    #[tokio::test]
    async fn logout_fences_in_flight_radar_transition() {
        let started=Arc::new(AtomicBool::new(false)); let flag=started.clone();
        let (origin, task)=fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login" => json_response(200,auth("access","refresh")),
            "/api/v1/auth/logout" => Response { status:204, body:String::new(), headers:vec![], delay_ms:0 },
            path if path.ends_with("/pause") => { flag.store(true,Ordering::SeqCst); let mut value=created_radar(); value["status"]=json!("paused"); Response { status:200, body:value.to_string(), headers:vec![], delay_ms:120 } },
            _ => json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap(); client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();
        let pending=tokio::spawn({ let client=client.clone(); async move { client.transition_radar("00000000-0000-4000-8000-000000000011".into(),ResourceStatus::Paused).await } });
        while !started.load(Ordering::SeqCst) { sleep(Duration::from_millis(5)).await; } client.logout().await.unwrap(); assert_eq!(pending.await.unwrap().err().unwrap().kind,"stale_session"); task.abort();
    }

    fn source(id: &str, source_type: &str) -> Value {
        json!({"id":id,"name":"Primary feed","source_type":source_type,"url":"https://example.com/feed","normalized_url":"https://example.com/feed","poll_interval_minutes":60,"status":"active"})
    }

    fn source_input() -> SourceCreateInput {
        SourceCreateInput { name:" Primary feed ".into(),source_type:SourceType::Rss,url:" https://example.com/feed ".into(),poll_interval_minutes:60 }
    }

    #[tokio::test]
    async fn source_collection_uses_typed_pagination_paths_idempotency_and_identity() {
        let radar="00000000-0000-4000-8000-000000000011"; let source_id="00000000-0000-4000-8000-000000000021"; let run="00000000-0000-4000-8000-000000000031"; let key="00000000-0000-4000-8000-000000000041";
        let source_value=source(source_id,"rss"); let created=source_value.clone();
        let (origin,task)=fake_server(Arc::new(move |request| match request.path.as_str() {
            "/api/v1/auth/login"=>json_response(200,auth("access","refresh")),
            "/api/v1/sources?page=2&page_size=20"=>{assert_eq!(request.method,"GET");json_response(200,json!({"items":[source_value.clone()],"page":2,"page_size":20,"total":21}))},
            "/api/v1/radars/00000000-0000-4000-8000-000000000011/sources?page=1&page_size=20"=>json_response(200,json!({"items":[source_value.clone()],"page":1,"page_size":20,"total":1})),
            "/api/v1/sources"=>{assert_eq!(request.method,"POST");assert_eq!(serde_json::from_str::<Value>(&request.body).unwrap(),json!({"name":"Primary feed","source_type":"rss","url":"https://example.com/feed","poll_interval_minutes":60}));json_response(201,created.clone())},
            "/api/v1/radars/00000000-0000-4000-8000-000000000011/sources/00000000-0000-4000-8000-000000000021"=>{assert!(matches!(request.method.as_str(),"POST"|"DELETE"));Response{status:204,body:String::new(),headers:vec![],delay_ms:0}},
            "/api/v1/sources/00000000-0000-4000-8000-000000000021/collect"=>{assert_eq!(request.method,"POST");assert_eq!(request.idempotency_key.as_deref(),Some("00000000-0000-4000-8000-000000000041"));Response{status:202,body:json!({"run_id":"00000000-0000-4000-8000-000000000031","status":"succeeded"}).to_string(),headers:vec![("Location".into(),"/api/v1/collection-runs/00000000-0000-4000-8000-000000000031".into())],delay_ms:0}},
            "/api/v1/collection-runs/00000000-0000-4000-8000-000000000031"=>json_response(200,json!({"id":"00000000-0000-4000-8000-000000000031","sourceId":"00000000-0000-4000-8000-000000000021","status":"succeeded","fetchedCount":3,"createdCount":2,"duplicateCount":1,"failedCount":0,"errorCode":null,"errorMessage":null})),
            _=>json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap();client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();
        assert_eq!(client.list_sources(2,20).await.unwrap().total,21);assert_eq!(client.list_radar_sources(radar.into(),1,20).await.unwrap().total,1);assert_eq!(client.create_source(source_input()).await.unwrap().id,source_id);
        client.bind_source(radar.into(),source_id.into(),true).await.unwrap();client.bind_source(radar.into(),source_id.into(),false).await.unwrap();
        assert_eq!(client.collect_source(source_id.into(),key.into()).await.unwrap().status,CollectionRunStatus::Succeeded);assert_eq!(client.collection_run(run.into(),source_id.into()).await.unwrap().created_count,2);task.abort();
    }

    #[tokio::test]
    async fn source_collection_rejects_bad_inputs_status_location_enum_and_identity() {
        assert!(ApiClient::pagination(0,20).is_err());assert!(ApiClient::pagination(1,101).is_err());
        assert!(SourceCreateInput{name:"x".into(),source_type:SourceType::Api,url:"https://example.com".into(),poll_interval_minutes:60}.payload().is_err());
        assert!(SourceCreateInput{name:"x".into(),source_type:SourceType::Url,url:"https://user:secret@example.com".into(),poll_interval_minutes:60}.payload().is_err());
        let collects=Arc::new(AtomicUsize::new(0));let count=collects.clone();
        let (origin,task)=fake_server(Arc::new(move |request| match request.path.as_str(){
            "/api/v1/auth/login"=>json_response(200,auth("access","refresh")),
            path if path.ends_with("/collect")=>{let call=count.fetch_add(1,Ordering::SeqCst);if call==0 {Response{status:200,body:json!({"run_id":"00000000-0000-4000-8000-000000000031","status":"queued"}).to_string(),headers:vec![],delay_ms:0}} else if call==1 {Response{status:202,body:json!({"run_id":"00000000-0000-4000-8000-000000000031","status":"queued"}).to_string(),headers:vec![("Location".into(),"https://evil.example/run".into())],delay_ms:0}} else {Response{status:202,body:json!({"run_id":"00000000-0000-4000-8000-000000000031","status":"mystery"}).to_string(),headers:vec![("Location".into(),"/api/v1/collection-runs/00000000-0000-4000-8000-000000000031".into())],delay_ms:0}}},
            path if path.contains("collection-runs")=>json_response(200,json!({"id":"00000000-0000-4000-8000-000000000099","sourceId":"00000000-0000-4000-8000-000000000021","status":"failed","fetchedCount":0,"createdCount":0,"duplicateCount":0,"failedCount":1,"errorCode":"failed","errorMessage":"failed"})),
            _=>json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap();client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();let source_id="00000000-0000-4000-8000-000000000021";let key="00000000-0000-4000-8000-000000000041";
        assert_eq!(client.collect_source("../x".into(),key.into()).await.err().unwrap().kind,"invalid_input");
        for _ in 0..3 {assert_eq!(client.collect_source(source_id.into(),key.into()).await.err().unwrap().kind,"invalid_response");}
        assert_eq!(client.collection_run("00000000-0000-4000-8000-000000000031".into(),source_id.into()).await.err().unwrap().kind,"invalid_response");task.abort();
    }

    fn intelligence(id:&str,radar_score:Value)->Value{json!({"id":id,"document_id":"00000000-0000-4000-8000-000000000051","radar_id":"00000000-0000-4000-8000-000000000011","title":"Verified signal","canonical_url":"https://example.com/item","summary":"Summary","category":"risk & policy","relevance":90,"importance":80,"novelty":70,"impact":60,"radar_score":radar_score,"recommendation":"must_read","reason":"Material change","status":"completed","error_code":null,"error_message":null,"pipeline_version":"v1","prompt_version":"p1","provider":"fixture","model":"fixture-model","bookmarked":false,"created_at":"2026-10-18T00:00:00Z","updated_at":"2026-10-18T00:00:01Z"})}
    fn intelligence_query()->IntelligenceQuery{IntelligenceQuery{page:2,page_size:10,radar_id:Some("00000000-0000-4000-8000-000000000011".into()),status:Some(AnalysisStatus::Completed),recommendation:Some(Recommendation::MustRead),category:Some(" risk & policy ".into()),min_score:Some(42.5)}}

    #[tokio::test]
    async fn intelligence_uses_encoded_typed_query_refresh_decimal_and_detail_identity(){
        let refreshes=Arc::new(AtomicUsize::new(0));let seen=refreshes.clone();let id="00000000-0000-4000-8000-000000000061";
        let (origin,task)=fake_server(Arc::new(move|request|match request.path.as_str(){
            "/api/v1/auth/login"=>json_response(200,auth("old","refresh")),
            "/api/v1/auth/refresh"=>{seen.fetch_add(1,Ordering::SeqCst);json_response(200,json!({"tokens":{"access_token":"new","refresh_token":"refresh-2"}}))},
            "/api/v1/intelligence?page=2&page_size=10&radar_id=00000000-0000-4000-8000-000000000011&status=completed&recommendation=must_read&category=risk+%26+policy&min_score=42.5" if request.authorization.as_deref()!=Some("Bearer new")=>json_response(401,json!({"error":{"code":"invalid_access_token","message":"Invalid","request_id":"00000000-0000-4000-8000-000000000099"}})),
            "/api/v1/intelligence?page=2&page_size=10&radar_id=00000000-0000-4000-8000-000000000011&status=completed&recommendation=must_read&category=risk+%26+policy&min_score=42.5"=>{assert_eq!(request.method,"GET");json_response(200,json!({"items":[intelligence("00000000-0000-4000-8000-000000000061",json!("88.50"))],"page":2,"page_size":10,"total":11}))},
            "/api/v1/intelligence/00000000-0000-4000-8000-000000000061"=>{let mut value=intelligence("00000000-0000-4000-8000-000000000061",json!(88.5));value["content"]=json!("<script>never execute</script>");value["author"]=json!("Author");value["language"]=json!("en");value["word_count"]=json!(5);json_response(200,value)},
            _=>json_response(404,json!({})),
        })).await;
        let client=ApiClient::new(&origin).unwrap();client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();let page=client.intelligence_list(intelligence_query()).await.unwrap();assert_eq!(page.items[0].id,id);assert_eq!(page.items[0].radar_score,Some(88.5));let detail=client.intelligence_detail(id.into(),"00000000-0000-4000-8000-000000000011".into()).await.unwrap();assert_eq!(detail.item.radar_score,Some(88.5));assert_eq!(detail.content,"<script>never execute</script>");assert_eq!(refreshes.load(Ordering::SeqCst),1);task.abort();
    }

    #[tokio::test]
    async fn intelligence_rejects_invalid_filters_pages_enums_scores_and_identity(){
        let calls=Arc::new(AtomicUsize::new(0));let count=calls.clone();let details=Arc::new(AtomicUsize::new(0));let detail_count=details.clone();let (origin,task)=fake_server(Arc::new(move|request|match request.path.as_str(){
            "/api/v1/auth/login"=>json_response(200,auth("access","refresh")),
            path if path.starts_with("/api/v1/intelligence?")=>{let call=count.fetch_add(1,Ordering::SeqCst);if call==0{json_response(200,json!({"items":[intelligence("00000000-0000-4000-8000-000000000061",json!(null))],"page":1,"page_size":10,"total":1}))}else if call==1{let mut value=intelligence("00000000-0000-4000-8000-000000000061",json!(50));value["status"]=json!("unknown");json_response(200,json!({"items":[value],"page":1,"page_size":10,"total":1}))}else if call==2{json_response(200,json!({"items":[intelligence("00000000-0000-4000-8000-000000000061",json!(101))],"page":1,"page_size":10,"total":1}))}else{Response{status:503,body:json!({"error":{"code":"unavailable","message":"Unavailable","request_id":"00000000-0000-4000-8000-000000000099"}}).to_string(),headers:vec![],delay_ms:0}}},
            path if path.starts_with("/api/v1/intelligence/")=>{if detail_count.fetch_add(1,Ordering::SeqCst)==0{return Response{status:404,body:json!({"error":{"code":"not_found","message":"Not found","request_id":"00000000-0000-4000-8000-000000000098"}}).to_string(),headers:vec![],delay_ms:0};}let mut value=intelligence("00000000-0000-4000-8000-000000000099",json!(50));value["content"]=json!("");value["author"]=Value::Null;value["language"]=Value::Null;value["word_count"]=json!(0);json_response(200,value)},
            _=>json_response(404,json!({})),
        })).await;let client=ApiClient::new(&origin).unwrap();client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();
        let mut invalid=intelligence_query();invalid.page=0;assert_eq!(client.intelligence_list(invalid).await.err().unwrap().kind,"invalid_input");let mut invalid=intelligence_query();invalid.radar_id=Some("../x".into());assert_eq!(client.intelligence_list(invalid).await.err().unwrap().kind,"invalid_input");let mut invalid=intelligence_query();invalid.category=Some("x".repeat(121));assert_eq!(client.intelligence_list(invalid).await.err().unwrap().kind,"invalid_input");let mut invalid=intelligence_query();invalid.min_score=Some(f64::NAN);assert_eq!(client.intelligence_list(invalid).await.err().unwrap().kind,"invalid_input");
        let basic=IntelligenceQuery{page:1,page_size:10,radar_id:None,status:None,recommendation:None,category:None,min_score:None};assert_eq!(client.intelligence_list(basic.clone()).await.unwrap().items[0].radar_score,None);assert_eq!(client.intelligence_list(basic.clone()).await.err().unwrap().kind,"invalid_response");assert_eq!(client.intelligence_list(basic.clone()).await.err().unwrap().kind,"invalid_response");let error=client.intelligence_list(basic).await.err().unwrap();assert_eq!(error.status,Some(503));assert_eq!(error.request_id.as_deref(),Some("00000000-0000-4000-8000-000000000099"));let error=client.intelligence_detail("00000000-0000-4000-8000-000000000061".into(),"00000000-0000-4000-8000-000000000011".into()).await.err().unwrap();assert_eq!(error.status,Some(404));assert_eq!(error.request_id.as_deref(),Some("00000000-0000-4000-8000-000000000098"));assert_eq!(client.intelligence_detail("00000000-0000-4000-8000-000000000061".into(),"00000000-0000-4000-8000-000000000011".into()).await.err().unwrap().kind,"invalid_response");task.abort();
    }

    #[tokio::test]
    async fn logout_fences_in_flight_intelligence(){let started=Arc::new(AtomicBool::new(false));let flag=started.clone();let(origin,task)=fake_server(Arc::new(move|request|match request.path.as_str(){"/api/v1/auth/login"=>json_response(200,auth("access","refresh")),"/api/v1/auth/logout"=>Response{status:204,body:String::new(),headers:vec![],delay_ms:0},path if path.starts_with("/api/v1/intelligence?")=>{flag.store(true,Ordering::SeqCst);Response{status:200,body:json!({"items":[],"page":1,"page_size":10,"total":0}).to_string(),headers:vec![],delay_ms:120}},_=>json_response(404,json!({}))})).await;let client=ApiClient::new(&origin).unwrap();client.authenticate(Operation::Login,"a@example.com".into(),"long-password".into(),None).await.unwrap();let pending=tokio::spawn({let client=client.clone();async move{client.intelligence_list(IntelligenceQuery{page:1,page_size:10,radar_id:None,status:None,recommendation:None,category:None,min_score:None}).await}});while !started.load(Ordering::SeqCst){sleep(Duration::from_millis(5)).await;}client.logout().await.unwrap();assert_eq!(pending.await.unwrap().err().unwrap().kind,"stale_session");task.abort();}
}
