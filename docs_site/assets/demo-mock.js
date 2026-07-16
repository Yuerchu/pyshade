/**
 * PyShade 文档站 demo mock(design.md §3.10):静态托管无 Python 后端,
 * 经 window.__PYSHADE_MOCK__ 拦截 /_shade/*,按 handlerId 复刻 docs_site/handlers.py
 * 的行为(用户已接受的双份维护;键集合与 EventRegistry 有对账测试防"缺口")。
 * 手写 ES2020,零构建,由 build.py 注入 <script> 于 app.js 之前。
 */
(() => {
  // 与 docs_site/state.py 的 DocsDemoState 默认值逐字段对应
  const state = {
    clicks: 0,
    click_note: "not clicked yet",
    progress: 40,
    confirmed: "not yet",
    submitted: "nothing yet",
    todos: [
      { id: 1, title: "Read the quickstart" },
      { id: 2, title: "Build your first page" },
    ],
  };
  const TARGET = "$s:DocsDemoState";
  const patch = (props) => ({ target: TARGET, props });

  const HANDLERS = {
    "ButtonPage.demo_btn.on_click": () => {
      state.clicks += 1;
      state.click_note = `clicked ${state.clicks} time(s)`;
      return [patch({ clicks: state.clicks, click_note: state.click_note })];
    },
    "EachPage.demo_todo_add.on_click": () => {
      const nextId = state.todos.reduce((max, todo) => Math.max(max, todo.id), 0) + 1;
      state.todos = [...state.todos, { id: nextId, title: `Task #${nextId}` }];
      return [patch({ todos: state.todos })];
    },
    "AlertDialogPage.demo_confirm.on_confirm": () => {
      state.confirmed = "confirmed!";
      return [patch({ confirmed: state.confirmed })];
    },
    "PasswordInputPage.demo_pw_submit.on_click": (payload) => {
      const count = Object.keys((payload && payload.values) || {}).length;
      state.submitted = `${count} field(s) received`;
      return [patch({ submitted: state.submitted })];
    },
  };

  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

  const sse = () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        // 首帧 = 快照(与 /_shade/push 契约一致);之后保持打开,不触发前端重连循环
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ patches: [patch({ ...state })] })}\n\n`));
      },
    });
    return new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } });
  };

  window.__PYSHADE_MOCK__ = async (path, init) => {
    if (path === "/_shade/push") {
      return sse();
    }
    const match = path.match(/^\/_shade\/event\/(.+)$/);
    if (match !== null) {
      const handler = HANDLERS[decodeURIComponent(match[1])];
      if (handler === undefined) {
        return json({ detail: `mock: unknown handler ${match[1]}` }, 404);
      }
      let payload = {};
      const body = init ? init.body : undefined;
      if (typeof body === "string") {
        try {
          payload = JSON.parse(body);
        } catch {
          payload = {};
        }
      } else if (body !== undefined && body !== null && !(body instanceof Uint8Array)) {
        payload = body;
      }
      return json({ patches: handler(payload) });
    }
    return undefined; // 其余路径留给真实 fetch(本地 dev 有真后端)
  };
})();
