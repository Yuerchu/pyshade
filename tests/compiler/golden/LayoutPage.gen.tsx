/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePageRuntime } from "@/runtime/page";

export function LayoutPage() {
  const rt = usePageRuntime();

  const [panels_0_0_0Value, setPanels_0_0_0Value] = useState<string>("");

  const collectValues = (_includeSensitive: boolean): Record<string, string | boolean> => ({
    panels_0_0_0: panels_0_0_0Value,
  });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("LayoutPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("LayoutPage.card", "title", "布局")}</CardTitle>
            <CardDescription>{rt.ov("LayoutPage.card", "description", "M2 Wave 3")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("LayoutPage.panels", "visible", true) && (
              <Tabs defaultValue="账号">
                <TabsList>
                  {rt.ov("LayoutPage.panels[0]", "visible", true) && (
                    <TabsTrigger value="账号">{rt.ov("LayoutPage.panels[0]", "label", "账号")}</TabsTrigger>
                  )}
                  {rt.ov("LayoutPage.panels[1]", "visible", true) && (
                    <TabsTrigger value="notify">{rt.ov("LayoutPage.panels[1]", "label", "通知")}</TabsTrigger>
                  )}
                </TabsList>
                {rt.ov("LayoutPage.panels[0]", "visible", true) && (
                  <TabsContent value="账号" className="flex flex-col gap-4">
                    {rt.ov("LayoutPage.panels[0][0]", "visible", true) && (
                      <Card className="w-full max-w-sm">
                        <CardHeader>
                          <CardTitle>{rt.ov("LayoutPage.panels[0][0]", "title", "账号信息")}</CardTitle>
                        </CardHeader>
                        <CardContent className="flex flex-col gap-4">
                          {rt.ov("LayoutPage.panels[0][0][0]", "visible", true) && (
                            <div className="grid gap-2">
                              <Label htmlFor="LayoutPage.panels[0][0][0]">{rt.ov("LayoutPage.panels[0][0][0]", "label", "用户名")}</Label>
                              <Input id="LayoutPage.panels[0][0][0]" disabled={rt.ov("LayoutPage.panels[0][0][0]", "disabled", false)} value={panels_0_0_0Value} onChange={(e) => setPanels_0_0_0Value(e.target.value)} />
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}
                  </TabsContent>
                )}
                {rt.ov("LayoutPage.panels[1]", "visible", true) && (
                  <TabsContent value="notify" className="flex flex-col gap-4">
                    {rt.ov("LayoutPage.panels[1][0]", "visible", true) && (
                      <p>{rt.ov("LayoutPage.panels[1][0]", "text", "通知设置")}</p>
                    )}
                  </TabsContent>
                )}
              </Tabs>
            )}
            {rt.ov("LayoutPage.faq", "visible", true) && (
              <Accordion type="multiple">
                {rt.ov("LayoutPage.faq[0]", "visible", true) && (
                  <AccordionItem value="什么是 PyShade?">
                    <AccordionTrigger>{rt.ov("LayoutPage.faq[0]", "title", "什么是 PyShade?")}</AccordionTrigger>
                    <AccordionContent className="flex flex-col gap-4">
                      {rt.ov("LayoutPage.faq[0][0]", "visible", true) && (
                        <p>{rt.ov("LayoutPage.faq[0][0]", "text", "纯 Python 桌面应用框架")}</p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                )}
                {rt.ov("LayoutPage.faq[1]", "visible", true) && (
                  <AccordionItem value="node">
                    <AccordionTrigger>{rt.ov("LayoutPage.faq[1]", "title", "需要 Node 吗?")}</AccordionTrigger>
                    <AccordionContent className="flex flex-col gap-4">
                      {rt.ov("LayoutPage.faq[1][0]", "visible", true) && (
                        <p>{rt.ov("LayoutPage.faq[1][0]", "text", "不需要,pip 装完即可打包")}</p>
                      )}
                    </AccordionContent>
                  </AccordionItem>
                )}
              </Accordion>
            )}
            {rt.ov("LayoutPage.logs", "visible", true) && (
              <ScrollArea style={{ height: "10rem" }} className="rounded-md border">
                <div className="flex flex-col gap-4 p-4">
                  {rt.ov("LayoutPage.logs[0]", "visible", true) && (
                    <p>{rt.ov("LayoutPage.logs[0]", "text", "日志 1")}</p>
                  )}
                  {rt.ov("LayoutPage.logs[1]", "visible", true) && (
                    <p>{rt.ov("LayoutPage.logs[1]", "text", "日志 2")}</p>
                  )}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
