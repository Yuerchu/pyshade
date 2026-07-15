/* 由 pyshade 编译器生成 — 请勿手改。 */
import { useState } from "react";

import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { usePageRuntime } from "@/runtime/page";

export function OverlayPage() {
  const rt = usePageRuntime({ boundProps: ["OverlayPage.settings_dialog.open"] });

  const [settings_openValue, setSettings_openValue] = useState<boolean>(false);
  const [edit_dialog_1Value, setEdit_dialog_1Value] = useState<string>("");

  const collectValues = (_includeSensitive: boolean): Record<string, string | boolean> => ({
    edit_dialog_1: edit_dialog_1Value,
    settings_dialog: settings_openValue,
    settings_open: settings_openValue,
  });

  return (
    <main className="flex min-h-svh items-center justify-center p-6">
      {rt.ov("OverlayPage.card", "visible", true) && (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>{rt.ov("OverlayPage.card", "title", "浮层")}</CardTitle>
            <CardDescription>{rt.ov("OverlayPage.card", "description", "M2 Wave 3")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {rt.ov("OverlayPage.edit_dialog", "visible", true) && (
              <Dialog>
                <DialogTrigger asChild>
                  <Button variant={rt.ov("OverlayPage.edit_dialog[0]", "variant", "outline")} size={rt.ov("OverlayPage.edit_dialog[0]", "size", "default")} disabled={rt.ov("OverlayPage.edit_dialog[0]", "disabled", false)}>
                    {rt.ov("OverlayPage.edit_dialog[0]", "text", "编辑资料")}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{rt.ov("OverlayPage.edit_dialog", "title", "编辑")}</DialogTitle>
                    <DialogDescription>{rt.ov("OverlayPage.edit_dialog", "description", "更新你的公开资料")}</DialogDescription>
                  </DialogHeader>
                  {rt.ov("OverlayPage.edit_dialog[1]", "visible", true) && (
                    <div className="grid gap-2">
                      <Label htmlFor="OverlayPage.edit_dialog[1]">{rt.ov("OverlayPage.edit_dialog[1]", "label", "昵称")}</Label>
                      <Input id="OverlayPage.edit_dialog[1]" disabled={rt.ov("OverlayPage.edit_dialog[1]", "disabled", false)} value={edit_dialog_1Value} onChange={(e) => setEdit_dialog_1Value(e.target.value)} />
                    </div>
                  )}
                  {rt.ov("OverlayPage.edit_dialog[2]", "visible", true) && (
                    <p className="text-muted-foreground">{rt.ov("OverlayPage.edit_dialog[2]", "text", "修改后立即生效")}</p>
                  )}
                </DialogContent>
              </Dialog>
            )}
            {rt.ov("OverlayPage.settings_dialog", "visible", true) && (
              <Dialog open={settings_openValue} onOpenChange={setSettings_openValue}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{rt.ov("OverlayPage.settings_dialog", "title", "设置")}</DialogTitle>
                  </DialogHeader>
                  {rt.ov("OverlayPage.settings_dialog[0]", "visible", true) && (
                    <p>{rt.ov("OverlayPage.settings_dialog[0]", "text", "设置内容")}</p>
                  )}
                </DialogContent>
              </Dialog>
            )}
            {rt.ov("OverlayPage.open_settings", "visible", true) && (
              <Button variant={rt.ov("OverlayPage.open_settings", "variant", "default")} size={rt.ov("OverlayPage.open_settings", "size", "default")} disabled={rt.ov("OverlayPage.open_settings", "disabled", false)}>
                {rt.ov("OverlayPage.open_settings", "text", "打开设置")}
              </Button>
            )}
            {rt.ov("OverlayPage.delete_confirm", "visible", true) && (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant={rt.ov("OverlayPage.delete_confirm[0]", "variant", "destructive")} size={rt.ov("OverlayPage.delete_confirm[0]", "size", "default")} disabled={rt.ov("OverlayPage.delete_confirm[0]", "disabled", false)}>
                    {rt.ov("OverlayPage.delete_confirm[0]", "text", "删除")}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{rt.ov("OverlayPage.delete_confirm", "title", "确定删除吗?")}</AlertDialogTitle>
                    <AlertDialogDescription>{rt.ov("OverlayPage.delete_confirm", "description", "此操作不可撤销")}</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel onClick={() => rt.fire("OverlayPage.delete_confirm.on_cancel", {})}>{rt.ov("OverlayPage.delete_confirm", "cancel_text", "取消")}</AlertDialogCancel>
                    <AlertDialogAction className="bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90" onClick={() => rt.fire("OverlayPage.delete_confirm.on_confirm", {})}>{rt.ov("OverlayPage.delete_confirm", "confirm_text", "删除")}</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
            {rt.ov("OverlayPage.hint", "visible", true) && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button variant={rt.ov("OverlayPage.hint[0]", "variant", "ghost")} size={rt.ov("OverlayPage.hint[0]", "size", "default")} disabled={rt.ov("OverlayPage.hint[0]", "disabled", false)}>
                      {rt.ov("OverlayPage.hint[0]", "text", "悬停看提示")}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side={rt.ov("OverlayPage.hint", "side", "right")}>{rt.ov("OverlayPage.hint", "text", "这是提示")}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </CardContent>
        </Card>
      )}
    </main>
  );
}
