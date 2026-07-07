import jsPDF from "jspdf";
import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
} from "docx";
import { saveAs } from "file-saver";
import { FinalRequirement } from "./requirementApi";

function buildFileName(projectName: string, ext: string) {
  const safeName = projectName.replace(/[^a-z0-9]+/gi, "_").toLowerCase();
  const date = new Date().toISOString().slice(0, 10);
  return `${safeName || "requirements"}_${date}.${ext}`;
}

/* ---------------- CSV ---------------- */
export function exportRequirementsAsCSV(
  requirements: FinalRequirement[],
  projectName: string
) {
  const header = "ID,Type,Requirement\n";
  const rows = requirements
    .map((item) => {
      const safeText = `"${item.requirement.replace(/"/g, '""')}"`;
      return `${item.id},${item.classification_type},${safeText}`;
    })
    .join("\n");

  const csvContent = header + rows;
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  saveAs(blob, buildFileName(projectName, "csv"));
}

/* ---------------- PDF ---------------- */
export function exportRequirementsAsPDF(
  requirements: FinalRequirement[],
  projectName: string
) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let y = 20;

  doc.setFontSize(16);
  doc.setFont("helvetica", "bold");
  doc.text(`${projectName} - Requirements`, pageWidth / 2, y, { align: "center" });
  y += 10;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  doc.text(`Generated: ${new Date().toLocaleString()}`, pageWidth / 2, y, {
    align: "center",
  });
  y += 12;

  const functional = requirements.filter((r) => r.classification_type === "FR");
  const nonFunctional = requirements.filter((r) => r.classification_type === "NFR");

  const writeSection = (title: string, items: FinalRequirement[]) => {
    doc.setFontSize(13);
    doc.setFont("helvetica", "bold");
    doc.text(title, 14, y);
    y += 8;

    doc.setFontSize(11);
    doc.setFont("helvetica", "normal");

    items.forEach((item, index) => {
      const lines = doc.splitTextToSize(`${index + 1}. ${item.requirement}`, 180);
      if (y + lines.length * 6 > 280) {
        doc.addPage();
        y = 20;
      }
      doc.text(lines, 14, y);
      y += lines.length * 6 + 4;
    });

    y += 6;
  };

  writeSection(`Functional Requirements (${functional.length})`, functional);
  writeSection(`Non-Functional Requirements (${nonFunctional.length})`, nonFunctional);

  doc.save(buildFileName(projectName, "pdf"));
}

/* ---------------- DOCX ---------------- */
export async function exportRequirementsAsDOCX(
  requirements: FinalRequirement[],
  projectName: string
) {
  const functional = requirements.filter((r) => r.classification_type === "FR");
  const nonFunctional = requirements.filter((r) => r.classification_type === "NFR");

  const buildSection = (title: string, items: FinalRequirement[]) => [
    new Paragraph({
      text: title,
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 300, after: 150 },
    }),
    ...items.map(
      (item, index) =>
        new Paragraph({
          children: [
            new TextRun({ text: `${index + 1}. `, bold: true }),
            new TextRun({ text: item.requirement }),
          ],
          spacing: { after: 120 },
        })
    ),
  ];

  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({
            text: `${projectName} - Requirements`,
            heading: HeadingLevel.HEADING_1,
            spacing: { after: 100 },
          }),
          new Paragraph({
            text: `Generated: ${new Date().toLocaleString()}`,
            spacing: { after: 300 },
          }),
          ...buildSection(`Functional Requirements (${functional.length})`, functional),
          ...buildSection(
            `Non-Functional Requirements (${nonFunctional.length})`,
            nonFunctional
          ),
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, buildFileName(projectName, "docx"));
}