export interface EncodedImageFile {
  base64: string;
  mimeType: string;
  filename: string;
}

// 1x1 transparent PNG fallback if canvas rendering is unavailable in headless environments.
const FALLBACK_SAMPLE_PNG_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";

export function readImageFileAsBase64(file: File): Promise<EncodedImageFile> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Nie udało się odczytać pliku graficznego."));
        return;
      }
      resolve({
        base64: reader.result,
        mimeType: file.type || "image/jpeg",
        filename: file.name,
      });
    };
    reader.onerror = () => reject(new Error("Błąd odczytu wybranego pliku."));
    reader.readAsDataURL(file);
  });
}

export function createSamplePylonImageBase64(): EncodedImageFile {
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = 360;
    canvas.height = 240;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.fillStyle = "#16213e";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = "#e63946";
      ctx.fillRect(0, 0, canvas.width, 44);

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 20px sans-serif";
      ctx.fillText("STACJA DEMO GDANSK", 20, 29);

      ctx.font = "bold 24px monospace";
      const rows: Array<[string, string, string]> = [
        ["PB95", "6.19", "#52b788"],
        ["PB98", "6.89", "#52b788"],
        ["ON", "6.29", "#f4a261"],
        ["LPG", "2.99", "#4cc9f0"],
      ];
      rows.forEach(([fuel, price, color], index) => {
        const y = 84 + index * 38;
        ctx.fillStyle = color;
        ctx.fillText(fuel, 28, y);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(price, 210, y);
      });

      return {
        base64: canvas.toDataURL("image/png"),
        mimeType: "image/png",
        filename: "sample-pylon-demo.png",
      };
    }
  }

  return {
    base64: FALLBACK_SAMPLE_PNG_DATA_URL,
    mimeType: "image/png",
    filename: "sample-pylon-demo.png",
  };
}
