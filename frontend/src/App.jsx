import { useTelemetrySocket } from "./hooks/useTelemetrySocket";
import { deriveMissionPhase } from "./utils/missionPhase";
import MissionHeader from "./components/MissionHeader";
import AlertPanel from "./components/AlertPanel";
import MissionPanel from "./components/MissionPanel";
import AltitudeHero from "./components/AltitudeHero";
import InstrumentGrid from "./components/InstrumentGrid";
import TelemetryCharts from "./components/TelemetryCharts";
import "./App.css";

export default function App() {
  const { latest, history, alerts, connectionState } = useTelemetrySocket();
  const phase = deriveMissionPhase(history);

  return (
    <div className="app">
      <MissionHeader
        connectionState={connectionState}
        latest={latest}
        link={alerts?.link}
      />

      <main className="app__main">
        <AlertPanel alerts={alerts} />
        <MissionPanel />
        <AltitudeHero latest={latest} phase={phase} />
        <InstrumentGrid latest={latest} />
        <TelemetryCharts history={history} />
      </main>
    </div>
  );
}
