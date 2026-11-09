import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AccountPage } from "./pages/AccountPage";
import { AuthPage } from "./pages/AuthPage";
import { FamilyFollowPage } from "./pages/FamilyFollowPage";
import { FamilyHomePage } from "./pages/FamilyHomePage";
import { FamilyPage } from "./pages/FamilyPage";
import { HistoryPage } from "./pages/HistoryPage";
import { JoinPage } from "./pages/JoinPage";
import { PlanPage } from "./pages/PlanPage";
import { SOSDemoPage } from "./pages/SOSDemoPage";
import { WalkPage } from "./pages/WalkPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PlanPage />} />
        <Route path="/walk" element={<WalkPage />} />
        <Route path="/walk/:id" element={<WalkPage />} />
        <Route path="/f/:id" element={<FamilyPage />} />
        <Route path="/family" element={<FamilyHomePage />} />
        <Route path="/family/follow/:fid/:jid" element={<FamilyFollowPage />} />
        <Route path="/join/:fid" element={<JoinPage />} />
        <Route path="/login" element={<AuthPage mode="in" />} />
        <Route path="/signup" element={<AuthPage mode="up" />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/sos-demo" element={<SOSDemoPage />} />
      </Routes>
    </BrowserRouter>
  );
}
