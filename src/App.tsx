import { useEffect, useState } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { MessageCircle } from "lucide-react";
import Layout from "./components/Layout";
import ChatSidebar from "./components/ChatSidebar";
import { getApiUrl } from "@/lib/api";
import Home from "./pages/Home";
import Projects from "./pages/Projects";
import Team from "./pages/Team";
import NotFound from "./pages/NotFound";
import Insights from "./pages/Insights";
import ProjectDetail from "./pages/ProjectDetail";
import HeatwaveDashboard from "./pages/HeatwaveDashboard";
import FloodDashboard from "./pages/FloodDashboard";

const CHAT_ENV_ENABLED = import.meta.env.VITE_CHAT_ENABLED !== "0";

const App = () => {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatAvailable, setChatAvailable] = useState(false);

  useEffect(() => {
    if (!CHAT_ENV_ENABLED) return;
    fetch(getApiUrl("/api/chat/status"))
      .then((r) => (r.ok ? r.json() : null))
      .then((s) => setChatAvailable(!!s?.enabled))
      .catch(() => setChatAvailable(false));
  }, []);

  return (
  <TooltipProvider>
    <Toaster />
    <Sonner />
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<Navigate to="/" replace />} />
          <Route path="/team" element={<Team />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/insights/:slug" element={<Insights />} />
          <Route path="/projects" element={<Projects />} />
          <Route
            path="/projects/heatwave-analysis"
            element={<HeatwaveDashboard />}
          />
          <Route
            path="/projects/flood-risk"
            element={<FloodDashboard />}
          />
          <Route
            path="/projects/:slug"
            element={<ProjectDetail />}
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
      {CHAT_ENV_ENABLED && chatAvailable && !chatOpen && (
        <button
          onClick={() => setChatOpen(true)}
          title="Flood Assistant"
          className="fixed bottom-5 right-5 z-[60] w-12 h-12 rounded-full bg-indigo-600 text-white shadow-xl hover:bg-indigo-500 transition-colors flex items-center justify-center"
        >
          <MessageCircle className="w-5 h-5" />
        </button>
      )}
      {CHAT_ENV_ENABLED && (
        <ChatSidebar open={chatOpen && chatAvailable} onClose={() => setChatOpen(false)} />
      )}
    </BrowserRouter>
  </TooltipProvider>
  );
};

export default App;
