/* 由 pyshade 编译器生成 — 请勿手改。 */
import { Fragment } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePageRuntime } from "@/runtime/page";
import type { EachChatMessage } from "../types.gen";

export function ChatPage() {
  const rt = usePageRuntime({ push: true });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("ChatPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("ChatPage.card", "title", "聊天")}</CardTitle>
            <CardDescription>{rt.ov("ChatPage.card", "description", "M2 Phase 6")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("ChatPage.messages", "visible", true) && rt.ov<EachChatMessage[]>("$s:EachChatState", "messages", [{"id": 1, "text": "你好", "mine": false}]).map((messagesItem: EachChatMessage, messagesIndex: number) => (
              <Fragment key={messagesItem.id}>
                <Card className="w-full max-w-sm">
                  <CardHeader>
                    <CardTitle>{"消息"}</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <p>{messagesItem.text}</p>
                    {(!messagesItem.mine) && (
                      <p className="text-muted-foreground">{"对方消息"}</p>
                    )}
                    {(messagesItem.mine) && (
                      <Button variant={"default"} size={"default"} disabled={false} onClick={() => rt.fire("ChatPage.messages.$t[0][2].on_click", { item_index: messagesIndex, item_key: messagesItem.id })}>
                        {"撤回"}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              </Fragment>
            ))}
            {rt.ov("ChatPage.tags", "visible", true) && rt.ov<string[]>("$s:EachChatState", "tags", ["alpha", "beta"]).map((tagsItem: string, tagsIndex: number) => (
              <Fragment key={tagsIndex}>
                <p>{tagsItem}</p>
              </Fragment>
            ))}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
