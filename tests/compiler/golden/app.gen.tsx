/* 由 pyshade 编译器生成 — 请勿手改。 */
import { ShadeAppProvider, ShadeRouter } from "@/runtime/app";
import { LoginPage } from "./pages/LoginPage.gen";

const PAGES = {
  LoginPage,
};

export default function App() {
  return (
    <ShadeAppProvider initial="LoginPage" pageNames={Object.keys(PAGES)} deepLink colorScheme="system">
      <ShadeRouter pages={PAGES} />
    </ShadeAppProvider>
  );
}
