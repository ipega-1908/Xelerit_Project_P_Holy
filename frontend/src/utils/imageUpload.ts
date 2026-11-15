export interface EncodedImageFile {
  base64: string;
  mimeType: string;
  filename: string;
}

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
