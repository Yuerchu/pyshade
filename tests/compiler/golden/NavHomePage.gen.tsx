/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePageRuntime } from "@/runtime/page";

export function NavHomePage() {
  const rt = usePageRuntime({ boundProps: ["NavHomePage.density.checked", "NavHomePage.hint.visible"] });

  const [denseValue, setDenseValue] = useState<boolean>(false);

  const collectValues = (_includeSensitive: boolean): Record<string, string | boolean> => ({
    density: denseValue,
    dense: denseValue,
  });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("NavHomePage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("NavHomePage.card", "title", "主页")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("NavHomePage.density", "visible", true) && (
              <div className="flex items-center gap-2">
                <Switch id="NavHomePage.density" checked={denseValue} disabled={rt.ov("NavHomePage.density", "disabled", false)} onCheckedChange={(checked) => { setDenseValue(checked) }} />
                <Label htmlFor="NavHomePage.density">{rt.ov("NavHomePage.density", "label", "紧凑模式")}</Label>
              </div>
            )}
            {(denseValue) && (
              <p>{rt.ov("NavHomePage.hint", "text", "紧凑模式已开启")}</p>
            )}
            {rt.ov("NavHomePage.goto", "visible", true) && (
              <Button variant={rt.ov("NavHomePage.goto", "variant", "outline")} size={rt.ov("NavHomePage.goto", "size", "default")} disabled={rt.ov("NavHomePage.goto", "disabled", false)} onClick={() => rt.navigate("NavDetailPage")}>
                {rt.ov("NavHomePage.goto", "text", "查看详情")}
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
