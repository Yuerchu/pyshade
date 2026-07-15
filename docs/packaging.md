# 打包分发指南(standalone 安装包)

把 PyShade 应用打成三平台原生安装包(Windows nsis/msi、macOS dmg/app、Linux deb)。
开发与运行只需要 Python(pytauri-wheel);**打包机需要 Python + Rust,依旧零 Node**。

## 前置条件(仅打包机)

```bash
# Rust 工具链(Windows 另需 Visual Studio Build Tools 的 MSVC 组件)
curl https://rustup.rs -sSf | sh
# tauri-cli(cargo 子命令,零 Node)
cargo install tauri-cli --version '^2' --locked
# Linux 另需 WebKitGTK 编译依赖
sudo apt-get install libwebkit2gtk-4.1-dev build-essential libssl-dev \
  libayatana-appindicator3-dev librsvg2-dev
```

## 两条命令

```bash
# 1. 生成 src-tauri 打包工程(一次性;productName/identifier 从 pyproject 与 Tauri.toml 推断)
pyshade init [--dir 项目根] [--product-name NAME] [--identifier ID] [--force]

# 2. 一键出安装包
pyshade package 模块:属性 [--dir 项目根] [--out dist-package] [--bundles nsis,msi]
```

`pyshade package` 依次做:前置体检(缺项一次性汇总)→ `pyshade bundle` 前端产物烤入
`src-tauri/frontend` → 下载便携 CPython(python-build-standalone,用户缓存 + stamp 增量)→
平台修补(macOS install_name_tool / Unix RUSTFLAGS)→ `uv pip install` 项目进内嵌解释器 →
compileall 预编译 → `cargo-tauri build` → 收集安装包到 `--out`。

## 常用参数与环境变量

| 项 | 说明 |
|---|---|
| `--bundles` | 逗号分隔;平台默认 `nsis,msi` / `dmg,app` / `deb`(AppImage 见下) |
| `--with REQ` | 追加 requirement;本地未发布依赖(path 源)必须显式给 wheel/目录 |
| `--skip-bundle` | 跳过前端构建(已自备 `src-tauri/frontend`) |
| `--fresh-pyembed` | 强制重建内嵌解释器 |
| `--python-version` / `--pbs-release` | 自选便携 CPython(配 `PYSHADE_CPYTHON_SHA256` 校验) |
| `PYSHADE_CPYTHON_MIRROR` | 替换 python-build-standalone 的下载前缀(镜像) |
| `PYSHADE_CPYTHON_ARCHIVE` | 离线 tarball 路径(仍做 sha256 校验) |
| `PYSHADE_CACHE_DIR` | 缓存根(esbuild 与 CPython 共用) |
| `PYSHADE_SMOKE=1` | 运行产物时 Ready 即退出(CI 冒烟) |

## 已知边界

- **AppImage 默认不出**:AppDir 会把 libpython 挪到 `usr/lib`(tauri#11898),rpath 已加
  第二条对冲但未在 CI 验证;`--bundles appimage` 可显式尝试。
- **签名/公证不在范围内**(M4+):macOS 未签名需右键打开或
  `xattr -d com.apple.quarantine`;Windows 有 SmartScreen 提示。
- **改 Python 代码后需重跑 package**:依赖以非 editable 方式装进内嵌解释器。
- 默认图标是占位图:替换 `src-tauri/icons/`(保持文件名)。
- Alpine/musl 不支持(python-build-standalone 是 glibc 构建)。

## CI 配方

仓库 `.github/workflows/release.yml` 即参考实现:tag 推送(`v*`)或手动触发,三平台 matrix
出安装包并附到 draft release;`taiki-e/install-action` 秒装 tauri-cli,`Swatinem/rust-cache` +
CPython tarball 缓存控制耗时。主 CI 的 `package-smoke` job 每次推送在 Windows 冒烟全链。
