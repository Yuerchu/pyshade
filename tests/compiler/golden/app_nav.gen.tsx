/* 由 pyshade 编译器生成 — 请勿手改。 */
import { ShadeAppProvider, ShadeRouter } from "@/runtime/app";
import { NavHomePage } from "./pages/NavHomePage.gen";
import { NavDetailPage } from "./pages/NavDetailPage.gen";

const PAGES = {
  NavHomePage,
  NavDetailPage,
};

const BOUND_PROPS = [
  "NavHomePage.density.checked",
  "NavHomePage.hint.visible",
];

export default function App() {
  return (
    <ShadeAppProvider initial="NavHomePage" boundProps={BOUND_PROPS} push pageNames={Object.keys(PAGES)} deepLink colorScheme="system">
      <ShadeRouter pages={PAGES} />
    </ShadeAppProvider>
  );
}
