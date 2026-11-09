import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthPage } from "./pages/AuthPage";
import { FamilyFollowPage } from "./pages/FamilyFollowPage";
import { FamilyPage } from "./pages/FamilyPage";
import { JoinPage } from "./pages/JoinPage";
import { PlanPage } from "./pages/PlanPage";
import { WalkPage } from "./pages/WalkPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* One map screen for the four tabs: switching tab keeps the map and slides the panel instead of reloading. */}
        <Route path="/:tab?" element={<PlanPage />} />
        <Route path="/walk" element={<WalkPage />} />
        <Route path="/walk/:id" element={<WalkPage />} />
        <Route path="/f/:id" element={<FamilyPage />} />
        <Route path="/family/follow/:fid/:jid" element={<FamilyFollowPage />} />
        <Route path="/join/:fid" element={<JoinPage />} />
        <Route path="/login" element={<AuthPage mode="in" />} />
        <Route path="/signup" element={<AuthPage mode="up" />} />
      </Routes>
    </BrowserRouter>
  );
}
