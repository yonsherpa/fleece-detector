import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { EspnLeagueProvider } from "./hooks/useEspnLeague";
import { LeagueProvider } from "./hooks/useLeagueSettings";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { LeaguePage } from "./pages/LeaguePage";
import { MovesPage } from "./pages/MovesPage";
import { RankingsPage } from "./pages/RankingsPage";
import { TradeAnalyzerPage } from "./pages/TradeAnalyzerPage";

export default function App() {
  return (
    <LeagueProvider>
      <EspnLeagueProvider>
        <BrowserRouter>
          <AppShell>
            <Routes>
              <Route path="/" element={<TradeAnalyzerPage />} />
              <Route path="/moves" element={<MovesPage />} />
              <Route path="/rankings" element={<RankingsPage />} />
              <Route path="/league" element={<LeaguePage />} />
              <Route
                path="/history"
                element={
                  <ComingSoonPage
                    title="Trade History"
                    phase="Planned"
                    description="Saved evaluations need persistence (SQLite), which isn't built yet. Until then, nothing you analyze is stored."
                  />
                }
              />
              <Route path="*" element={<ComingSoonPage title="Page not found" phase="404" description="That page doesn't exist." />} />
            </Routes>
          </AppShell>
        </BrowserRouter>
      </EspnLeagueProvider>
    </LeagueProvider>
  );
}
