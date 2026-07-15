/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { usePageRuntime } from "@/runtime/page";

export function FormControlsPage() {
  const rt = usePageRuntime({ boundProps: ["FormControlsPage.theme_radio.value", "FormControlsPage.loud.visible", "FormControlsPage.effort_echo.visible", "FormControlsPage.effort_echo.text"], push: true });

  const [themeValue, setThemeValue] = useState<string>("system");
  const [effortValue, setEffortValue] = useState<string>("");
  const [volumeValue, setVolumeValue] = useState<number>(30);

  const collectValues = (_includeSensitive: boolean): Record<string, string | boolean | number> => ({
    effort: effortValue,
    theme_radio: themeValue,
    volume: volumeValue,
    theme: themeValue,
  });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("FormControlsPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("FormControlsPage.card", "title", "表单控件")}</CardTitle>
            <CardDescription>{rt.ov("FormControlsPage.card", "description", "M2 Wave 2")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("FormControlsPage.effort", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="FormControlsPage.effort">{rt.ov("FormControlsPage.effort", "label", "思考力度")}</Label>
                <Select value={effortValue} onValueChange={(v) => { setEffortValue(v); rt.fire("FormControlsPage.effort.on_change", { value: v }) }} disabled={rt.ov("FormControlsPage.effort", "disabled", false)}>
                  <SelectTrigger id="FormControlsPage.effort">
                    <SelectValue placeholder={rt.ov("FormControlsPage.effort", "placeholder", "选择档位")} />
                  </SelectTrigger>
                  <SelectContent>
                    {rt.ov<{ value: string; label: string }[]>("FormControlsPage.effort", "options", [{"value": "low", "label": "low"}, {"value": "medium", "label": "medium"}, {"value": "high", "label": "high"}]).map((o) => (
                      <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {rt.ov("FormControlsPage.theme_radio", "visible", true) && (
              <div className="grid gap-2">
                <Label>{rt.ov("FormControlsPage.theme_radio", "label", "主题")}</Label>
                <RadioGroup value={themeValue} onValueChange={(v) => { setThemeValue(v) }} disabled={rt.ov("FormControlsPage.theme_radio", "disabled", false)}>
                  {rt.ov<{ value: string; label: string }[]>("FormControlsPage.theme_radio", "options", [{"value": "system", "label": "跟随系统"}, {"value": "light", "label": "亮色"}]).map((o) => (
                    <div key={o.value} className="flex items-center gap-2">
                      <RadioGroupItem id={"FormControlsPage.theme_radio" + "-" + o.value} value={o.value} />
                      <Label htmlFor={"FormControlsPage.theme_radio" + "-" + o.value}>{o.label}</Label>
                    </div>
                  ))}
                </RadioGroup>
              </div>
            )}
            {rt.ov("FormControlsPage.volume", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="FormControlsPage.volume">{rt.ov("FormControlsPage.volume", "label", "音量")}</Label>
                <Slider id="FormControlsPage.volume" min={rt.ov("FormControlsPage.volume", "min", 0)} max={rt.ov("FormControlsPage.volume", "max", 200)} step={rt.ov("FormControlsPage.volume", "step", 5)} disabled={rt.ov("FormControlsPage.volume", "disabled", false)} value={[volumeValue]} onValueChange={([v]) => setVolumeValue(v)} onValueCommit={([v]) => rt.fire("FormControlsPage.volume.on_change", { value: v })} />
              </div>
            )}
            {(volumeValue > 100) && (
              <Badge variant={rt.ov("FormControlsPage.loud", "variant", "default")}>{rt.ov("FormControlsPage.loud", "text", "响亮")}</Badge>
            )}
            {(effortValue !== "") && (
              <p className="text-muted-foreground">{"档位:" + effortValue}</p>
            )}
            {rt.ov("FormControlsPage.sync", "visible", true) && (
              <Progress value={rt.ov("$s:FormState", "sync_pct", 0)} />
            )}
            {rt.ov("FormControlsPage.save", "visible", true) && (
              <Button variant={rt.ov("FormControlsPage.save", "variant", "default")} size={rt.ov("FormControlsPage.save", "size", "default")} disabled={rt.ov("FormControlsPage.save", "disabled", false)} onClick={() => rt.fire("FormControlsPage.save.on_click", { values: collectValues(true) })}>
                {rt.ov("FormControlsPage.save", "text", "保存")}
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
