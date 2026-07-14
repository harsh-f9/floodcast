import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Projects from "./pages/Projects";
import Team from "./pages/Team";
import NotFound from "./pages/NotFound";
import Insights from "./pages/Insights";
import ProjectDetail from "./pages/ProjectDetail";
import HeatwaveDashboard from "./pages/HeatwaveDashboard";
import FloodDashboard from "./pages/FloodDashboard";

const App = () => (
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
    </BrowserRouter>
  </TooltipProvider>
);

export default App;
