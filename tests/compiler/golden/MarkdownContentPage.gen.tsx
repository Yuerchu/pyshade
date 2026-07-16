/* 由 pyshade 编译器生成 — 请勿手改。 */

import { usePageRuntime } from "@/runtime/page";

export function MarkdownContentPage() {
  const rt = usePageRuntime();

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("MarkdownContentPage.body", "visible", true) && (
        <section className="flex w-full max-w-3xl flex-col gap-4">
          {rt.ov("MarkdownContentPage.doc", "visible", true) && (
            <div className="prose prose-neutral dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: "<h1>标题</h1>\n<p><strong>加粗</strong>与 <code>行内代码</code></p>\n<table>\n<thead>\n<tr>\n  <th>列 A</th>\n  <th>列 B</th>\n</tr>\n</thead>\n<tbody>\n<tr>\n  <td>1</td>\n  <td>2</td>\n</tr>\n</tbody>\n</table>\n<pre class=\"shade-hl\"><code><span class=\"k\">def</span><span class=\"w\"> </span><span class=\"nf\">hi</span><span class=\"p\">()</span> <span class=\"o\">-&gt;</span> <span class=\"nb\">int</span><span class=\"p\">:</span>\n    <span class=\"k\">return</span> <span class=\"mi\">1</span></code></pre>\n" }} />
          )}
          {rt.ov("MarkdownContentPage.xss", "visible", true) && (
            <div className="prose prose-neutral dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: "<p>&lt;script&gt;alert(1)&lt;/script&gt; 与 &lt;img src=x onerror=alert(2)&gt;</p>\n" }} />
          )}
          {rt.ov("MarkdownContentPage.snippet", "visible", true) && (
            <pre className="shade-hl"><code dangerouslySetInnerHTML={{ __html: "<span class=\"k\">SELECT</span><span class=\"w\"> </span><span class=\"mi\">1</span><span class=\"p\">;</span>" }} /></pre>
          )}
          {rt.ov("MarkdownContentPage.plain", "visible", true) && (
            <pre className="shade-hl"><code dangerouslySetInnerHTML={{ __html: "纯文本,无高亮" }} /></pre>
          )}
        </section>
      )}
    </main>
  );
}
