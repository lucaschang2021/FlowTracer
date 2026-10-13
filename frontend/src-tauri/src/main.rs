#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // G1 deliberately registers no native commands or network/filesystem plugins.
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("FlowTracer could not start");
}
