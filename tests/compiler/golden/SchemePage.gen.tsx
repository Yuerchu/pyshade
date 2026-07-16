/* 由 pyshade 编译器生成 — 请勿手改。 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePageRuntime } from "@/runtime/page";

export function SchemePage() {
  const rt = usePageRuntime();

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("SchemePage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("SchemePage.card", "title", "配色")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("SchemePage.hint", "visible", true) && (
              <p>{rt.ov("SchemePage.hint", "text", "配色切换演示")}</p>
            )}
            {rt.ov("SchemePage.toggle", "visible", true) && (
              <Button variant={rt.ov("SchemePage.toggle", "variant", "ghost")} size={rt.ov("SchemePage.toggle", "size", "default")} disabled={rt.ov("SchemePage.toggle", "disabled", false)} onClick={() => rt.setColorScheme("toggle")}>
                {rt.ov("SchemePage.toggle", "text", "明暗切换")}
              </Button>
            )}
            {rt.ov("SchemePage.force_dark", "visible", true) && (
              <Button variant={rt.ov("SchemePage.force_dark", "variant", "default")} size={rt.ov("SchemePage.force_dark", "size", "default")} disabled={rt.ov("SchemePage.force_dark", "disabled", false)} onClick={() => rt.setColorScheme("dark")}>
                {rt.ov("SchemePage.force_dark", "text", "暗色")}
              </Button>
            )}
            {rt.ov("SchemePage.follow", "visible", true) && (
              <Button variant={rt.ov("SchemePage.follow", "variant", "default")} size={rt.ov("SchemePage.follow", "size", "default")} disabled={rt.ov("SchemePage.follow", "disabled", false)} onClick={() => rt.setColorScheme("system")}>
                {rt.ov("SchemePage.follow", "text", "跟随系统")}
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
