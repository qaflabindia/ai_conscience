import PDFKit
let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
var attrs = doc.documentAttributes ?? [:]
attrs[PDFDocumentAttribute.titleAttribute] = "Evidence-Gated Delegation for Agentic AI"
attrs[PDFDocumentAttribute.authorAttribute] = "Lakshminarasimhan Santhanam"
attrs[PDFDocumentAttribute.subjectAttribute] = "How to let an AI agent act only when the evidence justifies it, learn safely from verified mistakes, and prove it offline: a bank-reconciliation case study"
attrs[PDFDocumentAttribute.keywordsAttribute] = ["agentic AI","delegated authority","selective automation","risk-coverage","conformal risk control","evidence provenance","governed adaptation","bank reconciliation","AI governance","pre-registration"]
doc.documentAttributes = attrs

doc.write(to: URL(fileURLWithPath: a[2]))
let d2 = PDFDocument(url: URL(fileURLWithPath: a[2]))!
print("pages", d2.pageCount, "outline", d2.outlineRoot?.numberOfChildren ?? 0)
print(d2.documentAttributes![PDFDocumentAttribute.authorAttribute]!, "|", d2.documentAttributes![PDFDocumentAttribute.titleAttribute]!)
var links = 0
for i in 0..<d2.pageCount { links += d2.page(at:i)!.annotations.filter{ $0.type == "Link" }.count }
print("links", links)

