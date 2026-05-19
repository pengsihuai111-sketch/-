-- Add question_image_urls, ai_answer, and ai_solution fields to wrong_question_recognition_blocks table
-- These fields store images embedded in questions and AI-generated answers/solutions

ALTER TABLE wrong_question_recognition_blocks
ADD COLUMN question_image_urls TEXT DEFAULT NULL
COMMENT 'JSON array of image URLs embedded in the question';

ALTER TABLE wrong_question_recognition_blocks
ADD COLUMN ai_answer TEXT DEFAULT NULL
COMMENT 'AI generated answer for the question';

ALTER TABLE wrong_question_recognition_blocks
ADD COLUMN ai_solution TEXT DEFAULT NULL
COMMENT 'AI generated solution/explanation for the question';

-- Example question_image_urls: ["http://example.com/img1.png", "http://example.com/img2.png"]
