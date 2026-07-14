/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { usePageRuntime } from "@/runtime/page";

export function LoginPage() {
  const rt = usePageRuntime();

  const [usernameValue, setUsernameValue] = useState<string>("");
  const [rememberValue, setRememberValue] = useState<boolean>(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  const collectValues = (includeSensitive: boolean): Record<string, string | boolean> => ({
    username: usernameValue,
    remember: rememberValue,
    ...(includeSensitive ? { password: passwordRef.current?.value ?? "" } : {}),
  });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("LoginPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("LoginPage.card", "title", "登录")}</CardTitle>
            <CardDescription>{rt.ov("LoginPage.card", "description", "PyShade M0 演示")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("LoginPage.heading", "visible", true) && (
              <p>{rt.ov("LoginPage.heading", "text", "欢迎回来")}</p>
            )}
            {rt.ov("LoginPage.username", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="LoginPage.username">{rt.ov("LoginPage.username", "label", "用户名")}</Label>
                <Input id="LoginPage.username" placeholder={rt.ov("LoginPage.username", "placeholder", "请输入用户名")} disabled={rt.ov("LoginPage.username", "disabled", false)} value={usernameValue} onChange={(e) => setUsernameValue(e.target.value)} onBlur={() => rt.fire("LoginPage.username.on_change", { value: usernameValue })} />
              </div>
            )}
            {rt.ov("LoginPage.password", "visible", true) && (
              <div className="grid gap-2">
                <Label htmlFor="LoginPage.password">{rt.ov("LoginPage.password", "label", "密码")}</Label>
                <Input id="LoginPage.password" type="password" autoComplete="current-password" ref={passwordRef} placeholder={rt.ov("LoginPage.password", "placeholder", "请输入密码")} disabled={rt.ov("LoginPage.password", "disabled", false)} />
              </div>
            )}
            {rt.ov("LoginPage.remember", "visible", true) && (
              <div className="flex items-center gap-2">
                <Switch id="LoginPage.remember" checked={rememberValue} disabled={rt.ov("LoginPage.remember", "disabled", false)} onCheckedChange={(checked) => { setRememberValue(checked); rt.fire("LoginPage.remember.on_change", { value: checked }) }} />
                <Label htmlFor="LoginPage.remember">{rt.ov("LoginPage.remember", "label", "记住我")}</Label>
              </div>
            )}
            {rt.ov("LoginPage.submit", "visible", true) && (
              <Button variant={rt.ov("LoginPage.submit", "variant", "default")} size={rt.ov("LoginPage.submit", "size", "default")} disabled={rt.ov("LoginPage.submit", "disabled", false)} onClick={() => rt.fire("LoginPage.submit.on_click", { values: collectValues(true) })}>
                {rt.ov("LoginPage.submit", "text", "登录")}
              </Button>
            )}
            {rt.ov("LoginPage.greeting", "visible", true) && (
              <p className="text-muted-foreground">{rt.ov("LoginPage.greeting", "text", "")}</p>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
