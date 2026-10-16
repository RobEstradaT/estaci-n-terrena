import InstrumentCard from "./InstrumentCard";

function isFlagged(warnings, fieldName) {
  return (warnings ?? []).some((w) => w.startsWith(fieldName));
}

export default function InstrumentGrid({ latest }) {
  const warnings = latest?.warnings;

  const instruments = [
    {
      key: "temperature_c",
      label: "Temperatura",
      unit: "°C",
      value: latest?.temperature_c?.toFixed(1) ?? "--",
    },
    {
      key: "pressure_kpa",
      label: "Presión",
      unit: "kPa",
      value: latest?.pressure_kpa?.toFixed(1) ?? "--",
    },
    {
      key: "co2_ppm",
      label: "CO₂",
      unit: "ppm",
      value: latest?.co2_ppm?.toFixed(0) ?? "--",
    },
    {
      key: "acceleration_ms2",
      label: "Aceleración total",
      unit: "m/s²",
      value: latest?.acceleration_ms2?.toFixed(1) ?? "--",
    },
    {
      key: "rssi_dbm",
      label: "RSSI",
      unit: "dBm",
      value: latest?.rssi_dbm?.toFixed(0) ?? "--",
    },
    {
      key: "snr_db",
      label: "SNR",
      unit: "dB",
      value: latest?.snr_db?.toFixed(1) ?? "--",
    },
  ];

  return (
    <section className="instrument-grid">
      {instruments.map((inst) => (
        <InstrumentCard
          key={inst.key}
          label={inst.label}
          unit={inst.unit}
          value={inst.value}
          flagged={isFlagged(warnings, inst.key)}
        />
      ))}
    </section>
  );
}
