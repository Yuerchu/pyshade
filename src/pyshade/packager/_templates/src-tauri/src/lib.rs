use pyo3::prelude::*;

pub fn tauri_generate_context() -> tauri::Context {
    tauri::generate_context!()
}

#[pymodule(gil_used = false)]
#[pyo3(name = "ext_mod")]
pub mod ext_mod {
    use super::*;

    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        pytauri::pymodule_export(
            module,
            // context_factory:standalone 下忽略 Python 侧参数,frontendDist 已烤入二进制
            |_args, _kwargs| Ok(tauri_generate_context()),
            // builder_factory:PyShade 无自定义 Rust command,invoke_handler 由 Python 侧
            // AsgiIpcAdapter 经 BuilderArgs 传入
            |_args, _kwargs| Ok(tauri::Builder::default()),
        )
    }
}
