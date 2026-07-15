/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { usePageRuntime } from "@/runtime/page";

export function GalleryPage() {
  const rt = usePageRuntime({ boundProps: ["GalleryPage.agree_box.checked", "GalleryPage.agreed_badge.visible", "GalleryPage.note_echo.visible", "GalleryPage.note_echo.text"], push: true });

  const [agreeValue, setAgreeValue] = useState<boolean>(false);
  const [noteValue, setNoteValue] = useState<string>("");
  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("GalleryPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("GalleryPage.card", "title", "画廊")}</CardTitle>
            <CardDescription>{rt.ov("GalleryPage.card", "description", "M2 Wave 1")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("GalleryPage.heading", "visible", true) && (
              <p>{rt.ov("GalleryPage.heading", "text", "组件画廊")}</p>
            )}
            {rt.ov("GalleryPage.tag", "visible", true) && (
              <Badge variant={rt.ov("GalleryPage.tag", "variant", "secondary")}>{rt.ov("GalleryPage.tag", "text", "新功能")}</Badge>
            )}
            {rt.ov("GalleryPage.warn", "visible", true) && (
              <Alert variant={rt.ov("GalleryPage.warn", "variant", "destructive")}>
                <AlertTitle>{rt.ov("GalleryPage.warn", "title", "注意")}</AlertTitle>
                <AlertDescription>{rt.ov("GalleryPage.warn", "description", "这是一条演示提示")}</AlertDescription>
              </Alert>
            )}
            {rt.ov("GalleryPage.divider", "visible", true) && (
              <Separator orientation={rt.ov("GalleryPage.divider", "orientation", "horizontal")} />
            )}
            {rt.ov("GalleryPage.loading", "visible", true) && (
              <Skeleton style={{ width: "8rem", height: "1.25rem" }} />
            )}
            {rt.ov("GalleryPage.upload", "visible", true) && (
              <Progress value={rt.ov("$s:GalleryState", "upload_pct", 0)} />
            )}
            {rt.ov("GalleryPage.note", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="GalleryPage.note">{rt.ov("GalleryPage.note", "label", "备注")}</Label>
                <Textarea id="GalleryPage.note" placeholder={rt.ov("GalleryPage.note", "placeholder", "写点什么…")} rows={rt.ov("GalleryPage.note", "rows", 4)} disabled={rt.ov("GalleryPage.note", "disabled", false)} value={noteValue} onChange={(e) => setNoteValue(e.target.value)} onBlur={() => rt.fire("GalleryPage.note.on_change", { value: noteValue })} />
              </div>
            )}
            {rt.ov("GalleryPage.agree_box", "visible", true) && (
              <div className="flex items-center gap-2">
                <Checkbox id="GalleryPage.agree_box" checked={agreeValue} disabled={rt.ov("GalleryPage.agree_box", "disabled", false)} onCheckedChange={(checked) => { setAgreeValue(checked === true); rt.fire("GalleryPage.agree_box.on_change", { value: checked === true }) }} />
                <Label htmlFor="GalleryPage.agree_box">{rt.ov("GalleryPage.agree_box", "label", "同意条款")}</Label>
              </div>
            )}
            {(agreeValue) && (
              <Badge variant={rt.ov("GalleryPage.agreed_badge", "variant", "default")}>{rt.ov("GalleryPage.agreed_badge", "text", "已同意")}</Badge>
            )}
            {(noteValue !== "") && (
              <p className="text-muted-foreground">{"备注:" + noteValue}</p>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
