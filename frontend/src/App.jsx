import { Route, Routes, useLocation } from "react-router-dom";
import { Layout } from "./ui.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import StartTest from "./pages/StartTest.jsx";
import ExamRunner from "./pages/ExamRunner.jsx";
import Results from "./pages/Results.jsx";
import History from "./pages/History.jsx";
import Bank from "./pages/Bank.jsx";
import Review from "./pages/Review.jsx";

export default function App() {
  const loc = useLocation();
  // The test screen is full-bleed and distraction-free: no app navigation.
  if (loc.pathname.startsWith("/test/")) {
    return (
      <Routes>
        <Route path="/test/:id" element={<ExamRunner />} />
      </Routes>
    );
  }
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/start" element={<StartTest />} />
        <Route path="/results/:id" element={<Results />} />
        <Route path="/history" element={<History />} />
        <Route path="/bank" element={<Bank />} />
        <Route path="/review" element={<Review />} />
        <Route path="*" element={<p className="muted">Page not found.</p>} />
      </Routes>
    </Layout>
  );
}
