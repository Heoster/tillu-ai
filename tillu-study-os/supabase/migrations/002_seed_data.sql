-- =============================================================================
-- Tillu AI Study OS — CBSE Class 12 Seed Data
-- Migration: 002_seed_data.sql
-- =============================================================================
-- Inserts the five CBSE Class 12 subjects and all their board exam chapters
-- with correct board weightage values.
--
-- Insertion order:
--   1. subjects  (Physics, Chemistry, Mathematics, English, Computer Science)
--   2. chapters  (per subject, via CTE UUID lookups)
--
-- Uses ON CONFLICT DO NOTHING so the migration is safe to re-run.
-- =============================================================================

-- =============================================================================
-- 1. Subjects
-- =============================================================================
INSERT INTO subjects (name) VALUES
    ('Physics'),
    ('Chemistry'),
    ('Mathematics'),
    ('English'),
    ('Computer Science')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. Chapters — Physics
--    Total theory marks: 70
-- =============================================================================
WITH phys AS (SELECT id FROM subjects WHERE name = 'Physics')
INSERT INTO chapters (subject_id, name, board_weightage) VALUES
    ((SELECT id FROM phys), 'Electric Charges and Fields',           8),
    ((SELECT id FROM phys), 'Electrostatic Potential and Capacitance', 7),
    ((SELECT id FROM phys), 'Current Electricity',                   7),
    ((SELECT id FROM phys), 'Moving Charges and Magnetism',          8),
    ((SELECT id FROM phys), 'Magnetism and Matter',                  5),
    ((SELECT id FROM phys), 'Electromagnetic Induction',             8),
    ((SELECT id FROM phys), 'Alternating Current',                   7),
    ((SELECT id FROM phys), 'Electromagnetic Waves',                 5),
    ((SELECT id FROM phys), 'Ray Optics and Optical Instruments',   10),
    ((SELECT id FROM phys), 'Wave Optics',                           7),
    ((SELECT id FROM phys), 'Dual Nature of Radiation and Matter',   6),
    ((SELECT id FROM phys), 'Atoms',                                 4),
    ((SELECT id FROM phys), 'Nuclei',                                4),
    ((SELECT id FROM phys), 'Semiconductor Electronics',             7),
    ((SELECT id FROM phys), 'Communication Systems',                 5)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 3. Chapters — Chemistry
--    Total theory marks: 70
-- =============================================================================
WITH chem AS (SELECT id FROM subjects WHERE name = 'Chemistry')
INSERT INTO chapters (subject_id, name, board_weightage) VALUES
    ((SELECT id FROM chem), 'Solutions',                              7),
    ((SELECT id FROM chem), 'Electrochemistry',                       9),
    ((SELECT id FROM chem), 'Chemical Kinetics',                      7),
    ((SELECT id FROM chem), 'd and f Block Elements',                 8),
    ((SELECT id FROM chem), 'Coordination Compounds',                 8),
    ((SELECT id FROM chem), 'Haloalkanes and Haloarenes',             6),
    ((SELECT id FROM chem), 'Alcohols, Phenols and Ethers',           6),
    ((SELECT id FROM chem), 'Aldehydes, Ketones and Carboxylic Acids',8),
    ((SELECT id FROM chem), 'Amines',                                 6),
    ((SELECT id FROM chem), 'Biomolecules',                           4),
    ((SELECT id FROM chem), 'Polymers',                               3),
    ((SELECT id FROM chem), 'Chemistry in Everyday Life',             3)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 4. Chapters — Mathematics
--    Total marks: 80
-- =============================================================================
WITH math AS (SELECT id FROM subjects WHERE name = 'Mathematics')
INSERT INTO chapters (subject_id, name, board_weightage) VALUES
    ((SELECT id FROM math), 'Relations and Functions',               8),
    ((SELECT id FROM math), 'Inverse Trigonometric Functions',       5),
    ((SELECT id FROM math), 'Matrices',                             10),
    ((SELECT id FROM math), 'Determinants',                          8),
    ((SELECT id FROM math), 'Continuity and Differentiability',      8),
    ((SELECT id FROM math), 'Applications of Derivatives',           8),
    ((SELECT id FROM math), 'Integrals',                             8),
    ((SELECT id FROM math), 'Applications of Integrals',             5),
    ((SELECT id FROM math), 'Differential Equations',                5),
    ((SELECT id FROM math), 'Vector Algebra',                        6),
    ((SELECT id FROM math), 'Three Dimensional Geometry',            6),
    ((SELECT id FROM math), 'Linear Programming',                    5),
    ((SELECT id FROM math), 'Probability',                           8)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 5. Chapters — English
--    Total marks: 80
-- =============================================================================
WITH eng AS (SELECT id FROM subjects WHERE name = 'English')
INSERT INTO chapters (subject_id, name, board_weightage) VALUES
    ((SELECT id FROM eng), 'Reading Comprehension',                 20),
    ((SELECT id FROM eng), 'Writing Skills - Notice/Formal Letter',  8),
    ((SELECT id FROM eng), 'Writing Skills - Advertisement/Article', 8),
    ((SELECT id FROM eng), 'Grammar',                               16),
    ((SELECT id FROM eng), 'Literature - Flamingo Prose',           14),
    ((SELECT id FROM eng), 'Literature - Flamingo Poetry',           8),
    ((SELECT id FROM eng), 'Literature - Vistas',                    6)
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 6. Chapters — Computer Science
--    Total marks: 70
-- =============================================================================
WITH cs AS (SELECT id FROM subjects WHERE name = 'Computer Science')
INSERT INTO chapters (subject_id, name, board_weightage) VALUES
    ((SELECT id FROM cs), 'Python Revision Tour',                    5),
    ((SELECT id FROM cs), 'Functions',                               8),
    ((SELECT id FROM cs), 'File Handling',                           7),
    ((SELECT id FROM cs), 'Data Structures - Stack',                 7),
    ((SELECT id FROM cs), 'Data Structures - Queue',                 5),
    ((SELECT id FROM cs), 'Searching and Sorting',                   6),
    ((SELECT id FROM cs), 'Database Management System',             10),
    ((SELECT id FROM cs), 'SQL Queries',                            10),
    ((SELECT id FROM cs), 'Networking Concepts',                     7),
    ((SELECT id FROM cs), 'Internet and Web Technologies',           5)
ON CONFLICT DO NOTHING;
