#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod api;

fn main() {
    tauri::Builder::default()
        .manage(api::Bridge::from_environment())
        .invoke_handler(tauri::generate_handler![
            api::bridge_status,
            api::health_ready,
            api::auth_register,
            api::auth_login,
            api::auth_logout,
            api::auth_refresh,
            api::users_me,
            api::radars_list,
            api::radars_create,
        ])
        .run(tauri::generate_context!())
        .expect("FlowTracer could not start");
}
