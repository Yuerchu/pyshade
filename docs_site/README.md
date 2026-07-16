# docs_site

PyShade 文档站(M4 dogfooding,design.md §3.10):双 locale(en/zh),30 个组件页由
`pyshade.docs.introspect` + demo 工厂动态生成,静态托管在 Cloudflare Pages。

## 本地预览(真 Python 后端)

```bash
PYTHONPATH=docs_site/src PYSHADE_DOCS_LOCALE=en uv run pyshade dev docs_site.app:app
```

## 全站构建(静态形态,含 demo mock / llms.txt / md 快照)

```bash
PYTHONPATH=docs_site/src uv run python docs_site/build.py --out dist-docs
uv run python -m http.server -d dist-docs 8000   # 本地静态预览
```

## 内容维护

- 组件字段中文描述:`content/zh/props.toml`;类 docstring 英译:`content/en/extra.toml`。
  加组件/加字段后 `tests/docs_site` 对账测试会红,跑 `uv run python scripts/sync_docs_content.py`
  补键(占位为原文),再人工翻译。
- 服务端 demo 改动(`handlers.py`)必须同步 `assets/demo-mock.js`(handlerId 键集合有对账测试;
  行为一致性靠 `pyshade dev` 真后端人工走查——静态站是 JS 模拟,这是显式接受的双份维护)。
- 指南长文:`content/{en,zh}/guides/*.md`。

## Cloudflare Pages 部署(一次性配置)

CI(`.github/workflows/docs.yml`)在 push main 时构建;配好以下 secrets 后自动部署,
未配置时只构建并上传 `docs-site` artifact:

1. Cloudflare dashboard(或 `wrangler pages project create pyshade-docs`)建 Pages 项目
   `pyshade-docs`(Direct Upload 模式);
2. My Profile → API Tokens → Create Custom Token,权限 `Account → Cloudflare Pages → Edit`;
3. dashboard 首页右栏复制 Account ID;
4. GitHub 仓库 Settings → Secrets and variables → Actions:新增 `CLOUDFLARE_API_TOKEN`、
   `CLOUDFLARE_ACCOUNT_ID`;
5. (可选)Pages 项目绑自定义域后,仓库 Variables 加 `PYSHADE_DOCS_BASE_URL` 指向新域
   (影响语言切换 Link 与 llms.txt 内链)。

## 已知小瑕疵

- 无 favicon(浏览器控制台 404,无功能影响)——bundle 三件套契约没有静态资产管线
  (design.md §6 的 Image/资产开放问题),有管线后一并解。
