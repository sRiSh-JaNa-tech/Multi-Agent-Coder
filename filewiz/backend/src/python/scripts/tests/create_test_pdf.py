from reportlab.pdfgen import canvas
import os

def create_pdf(filename):
    c = canvas.Canvas(filename)
    c.drawString(100, 750, "Page 1")
    c.showPage()
    c.drawString(100, 750, "Page 2")
    c.showPage()
    c.drawString(100, 750, "Page 3")
    c.showPage()
    c.save()

if __name__ == "__main__":
    create_pdf("test.pdf")
    print("Created test.pdf")
