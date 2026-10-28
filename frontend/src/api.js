export const API_URL = "http://localhost:8000";

export function errorMessage(err) {
  return err instanceof TypeError ? "No se pudo conectar con el backend." : err.message;
}

export async function request(path, options) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    let message = `Error ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // La respuesta no traía JSON; se queda el mensaje genérico.
    }
    throw new Error(message);
  }
  return response.json();
}
