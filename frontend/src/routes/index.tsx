import { createFileRoute } from "@tanstack/react-router";
import { PdfRagApp } from "@/components/pdf-rag/PdfRagApp";

export const Route = createFileRoute("/")({
  component: PdfRagApp,
});
