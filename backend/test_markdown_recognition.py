"""Test markdown-based PDF recognition"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.pdf_to_markdown import pdf_to_markdown, extract_questions_from_markdown
from app.utils.deepseek import call_text_llm


async def test_pdf_recognition(pdf_path: str):
    """Test PDF to markdown recognition"""
    print(f"Testing PDF: {pdf_path}")

    # Read PDF file
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()

    print(f"PDF size: {len(pdf_bytes)} bytes")

    # Step 1: Convert to markdown
    print("\n=== Step 1: Converting PDF to Markdown ===")
    try:
        markdown_text = pdf_to_markdown(pdf_bytes, max_pages=30)
        print(f"Markdown length: {len(markdown_text)} chars")
        print("\nFirst 500 chars of markdown:")
        print(markdown_text[:500])
        print("...")
    except Exception as e:
        print(f"ERROR converting to markdown: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Extract questions
    print("\n=== Step 2: Extracting questions with LLM ===")
    try:
        questions = await extract_questions_from_markdown(markdown_text, call_text_llm)
        print(f"\nExtracted {len(questions)} questions:")

        for i, q in enumerate(questions, 1):
            print(f"\n--- Question {i} ---")
            print(f"Question No: {q.get('question_no', 'N/A')}")
            print(f"Type: {q.get('question_type', 'N/A')}")
            print(f"Text: {q.get('question_text', 'N/A')[:100]}...")
            print(f"Answer: {q.get('answer', 'N/A')[:100]}...")
            print(f"Has Image: {q.get('has_image', False)}")
            print(f"Confidence: {q.get('confidence', 0)}")

    except Exception as e:
        print(f"ERROR extracting questions: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n=== Test completed successfully ===")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_markdown_recognition.py <pdf_file_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    asyncio.run(test_pdf_recognition(pdf_path))
