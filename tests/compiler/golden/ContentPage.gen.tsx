/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePageRuntime } from "@/runtime/page";

export function ContentPage() {
  const rt = usePageRuntime({ boundProps: ["ContentPage.fine.visible", "ContentPage.toggle.checked"] });

  const [detailedValue, setDetailedValue] = useState<boolean>(false);
  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("ContentPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("ContentPage.card", "title", "内容")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("ContentPage.title", "visible", true) && (
              <h1 className="scroll-m-20 text-4xl font-extrabold tracking-tight">{rt.ov("ContentPage.title", "text", "内容组件")}</h1>
            )}
            {rt.ov("ContentPage.section", "visible", true) && (
              <h2 className="scroll-m-20 text-3xl font-semibold tracking-tight">{rt.ov("ContentPage.section", "text", "小节")}</h2>
            )}
            {(detailedValue) && (
              <h4 className="scroll-m-20 text-xl font-semibold tracking-tight">{rt.ov("ContentPage.fine", "text", "细则")}</h4>
            )}
            {rt.ov("ContentPage.toggle", "visible", true) && (
              <div className="flex items-center gap-2">
                <Switch id="ContentPage.toggle" checked={detailedValue} disabled={rt.ov("ContentPage.toggle", "disabled", false)} onCheckedChange={(checked) => { setDetailedValue(checked) }} />
                <Label htmlFor="ContentPage.toggle">{rt.ov("ContentPage.toggle", "label", "展开细则")}</Label>
              </div>
            )}
            {rt.ov("ContentPage.home", "visible", true) && (
              <a href={"https://example.com/pyshade"} target="_blank" rel="noreferrer" className="font-medium underline underline-offset-4">{"项目主页"}</a>
            )}
            {rt.ov("ContentPage.mail", "visible", true) && (
              <a href={"mailto:hi@example.com"} target="_blank" rel="noreferrer" className="font-medium underline underline-offset-4">{"联系我们"}</a>
            )}
            {rt.ov("ContentPage.note", "visible", true) && (
              <p className="text-muted-foreground">{rt.ov("ContentPage.note", "text", "Heading/Link 演示")}</p>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
