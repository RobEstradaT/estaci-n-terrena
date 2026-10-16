import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

const GRID_COLOR = "#1a2540";
const AXIS_COLOR = "#7d8bab";

function ChartPanel({ title, data, lines }) {
  return (
    <div className="chart-panel">
      <span className="label">{title}</span>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid stroke={GRID_COLOR} vertical={false} />
          <XAxis
            dataKey="mission_time_s"
            stroke={AXIS_COLOR}
            tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
            tickFormatter={(t) => `${t}s`}
            minTickGap={30}
          />
          <YAxis
            stroke={AXIS_COLOR}
            tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
            width={48}
          />
          <Tooltip
            contentStyle={{
              background: "#111a2b",
              border: "1px solid #223052",
              borderRadius: 2,
              fontFamily: "JetBrains Mono",
              fontSize: 12,
            }}
            labelFormatter={(t) => `t = ${t}s`}
          />
          {lines.map((line) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              name={line.name}
              stroke={line.color}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function TelemetryCharts({ history }) {
  return (
    <section className="telemetry-charts">
      <ChartPanel
        title="Altitud (m)"
        data={history}
        lines={[{ dataKey: "altitude_m", name: "Altitud", color: "#4fd1c5" }]}
      />
      <ChartPanel
        title="Velocidad vertical (m/s)"
        data={history}
        lines={[{ dataKey: "velocity_ms", name: "Velocidad", color: "#f5b942" }]}
      />
      <ChartPanel
        title="Temperatura (°C)"
        data={history}
        lines={[{ dataKey: "temperature_c", name: "Temperatura", color: "#f2545b" }]}
      />
      <ChartPanel
        title="Presión (kPa)"
        data={history}
        lines={[{ dataKey: "pressure_kpa", name: "Presión", color: "#4fd1c5" }]}
      />
      <ChartPanel
        title="Aceleración total (m/s²)"
        data={history}
        lines={[{ dataKey: "acceleration_ms2", name: "Aceleración", color: "#c084fc" }]}
      />
      <ChartPanel
        title="RSSI (dBm) / SNR (dB)"
        data={history}
        lines={[
          { dataKey: "rssi_dbm", name: "RSSI", color: "#52d17c" },
          { dataKey: "snr_db", name: "SNR", color: "#f5b942" },
        ]}
      />
    </section>
  );
}
