/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePageRuntime } from "@/runtime/page";

export function SettingsPage() {
  const rt = usePageRuntime({ boundProps: ["SettingsPage.thinking_switch.checked", "SettingsPage.dark_switch.checked", "SettingsPage.effort.disabled", "SettingsPage.nickname.value", "SettingsPage.greeting.visible", "SettingsPage.greeting.text", "SettingsPage.echo.visible", "SettingsPage.echo.text", "SettingsPage.both.visible"] });

  const [thinkingValue, setThinkingValue] = useState<boolean>(true);
  const [darkValue, setDarkValue] = useState<boolean>(false);
  const [nickValue, setNickValue] = useState<string>("");
  const [effortValue, setEffortValue] = useState<string>("");

  const collectValues = (_includeSensitive: boolean): Record<string, string | boolean> => ({
    thinking_switch: thinkingValue,
    dark_switch: darkValue,
    effort: effortValue,
    nickname: nickValue,
    thinking: thinkingValue,
    dark: darkValue,
    nick: nickValue,
  });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("SettingsPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("SettingsPage.card", "title", "设置")}</CardTitle>
            <CardDescription>{rt.ov("SettingsPage.card", "description", "M1 表达式演示")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("SettingsPage.thinking_switch", "visible", true) && (
              <div className="flex items-center gap-2">
                <Switch id="SettingsPage.thinking_switch" checked={thinkingValue} disabled={rt.ov("SettingsPage.thinking_switch", "disabled", false)} onCheckedChange={(checked) => { setThinkingValue(checked) }} />
                <Label htmlFor="SettingsPage.thinking_switch">{rt.ov("SettingsPage.thinking_switch", "label", "思考模式")}</Label>
              </div>
            )}
            {rt.ov("SettingsPage.dark_switch", "visible", true) && (
              <div className="flex items-center gap-2">
                <Switch id="SettingsPage.dark_switch" checked={darkValue} disabled={rt.ov("SettingsPage.dark_switch", "disabled", false)} onCheckedChange={(checked) => { setDarkValue(checked) }} />
                <Label htmlFor="SettingsPage.dark_switch">{rt.ov("SettingsPage.dark_switch", "label", "深色模式")}</Label>
              </div>
            )}
            {rt.ov("SettingsPage.effort", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="SettingsPage.effort">{rt.ov("SettingsPage.effort", "label", "思考力度")}</Label>
                <Input id="SettingsPage.effort" placeholder={rt.ov("SettingsPage.effort", "placeholder", "low / medium / high")} disabled={!thinkingValue} value={effortValue} onChange={(e) => setEffortValue(e.target.value)} />
              </div>
            )}
            {rt.ov("SettingsPage.nickname", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="SettingsPage.nickname">{rt.ov("SettingsPage.nickname", "label", "昵称")}</Label>
                <Input id="SettingsPage.nickname" placeholder={rt.ov("SettingsPage.nickname", "placeholder", null)} disabled={rt.ov("SettingsPage.nickname", "disabled", false)} value={nickValue} onChange={(e) => setNickValue(e.target.value)} />
              </div>
            )}
            {(nickValue !== "") && (
              <p>{("你好," + nickValue) + "!"}</p>
            )}
            {(effortValue !== "") && (
              <p className="text-muted-foreground">{"输入了:" + effortValue}</p>
            )}
            {(thinkingValue && darkValue) && (
              <p className="text-muted-foreground">{rt.ov("SettingsPage.both", "text", "思考与深色已同时开启")}</p>
            )}
            {rt.ov("SettingsPage.save", "visible", true) && (
              <Button variant={rt.ov("SettingsPage.save", "variant", "default")} size={rt.ov("SettingsPage.save", "size", "default")} disabled={rt.ov("SettingsPage.save", "disabled", false)} onClick={() => rt.fire("SettingsPage.save.on_click", { values: collectValues(true) })}>
                {rt.ov("SettingsPage.save", "text", "保存")}
              </Button>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
