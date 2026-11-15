-- Candidate count by primary technology
SELECT primary_technology, COUNT(*) AS candidate_count
FROM candidates
GROUP BY primary_technology
ORDER BY candidate_count DESC;

-- Open opportunities by hiring company
SELECT co.company_name, COUNT(j.job_id) AS open_jobs
FROM jobs j
JOIN companies co ON co.company_id = j.company_id
WHERE j.status = 'OPEN'
GROUP BY co.company_id, co.company_name
ORDER BY open_jobs DESC;

-- Applications by workflow stage
SELECT application_status, COUNT(*) AS application_count
FROM applications
GROUP BY application_status
ORDER BY application_count DESC;

-- Recruitment funnel
SELECT
    COUNT(*) AS applications,
    SUM(application_status IN ('SHORTLISTED', 'INTERVIEW_SCHEDULED', 'INTERVIEWED',
                               'SELECTED', 'OFFERED', 'JOINED')) AS shortlisted,
    SUM(application_status IN ('INTERVIEW_SCHEDULED', 'INTERVIEWED',
                               'SELECTED', 'OFFERED', 'JOINED')) AS interviewed,
    SUM(application_status IN ('SELECTED', 'OFFERED', 'JOINED')) AS selected,
    SUM(application_status = 'JOINED') AS joined
FROM applications;

-- Company-wise completed placements
SELECT co.company_name, COUNT(p.placement_id) AS placed_count
FROM placements p
JOIN companies co ON co.company_id = p.company_id
WHERE p.joining_status = 'JOINED'
GROUP BY co.company_id, co.company_name
ORDER BY placed_count DESC;

-- Technology-wise completed placements
SELECT c.primary_technology, COUNT(p.placement_id) AS placed_count
FROM placements p
JOIN candidates c ON c.candidate_id = p.candidate_id
WHERE p.joining_status = 'JOINED'
GROUP BY c.primary_technology
ORDER BY placed_count DESC;

-- Recruiter activity
SELECT u.full_name AS recruiter, COUNT(a.application_id) AS applications_handled
FROM users u
LEFT JOIN applications a ON a.assigned_recruiter_id = u.user_id
JOIN roles r ON r.role_id = u.role_id
WHERE r.role_code = 'RECRUITER'
GROUP BY u.user_id, u.full_name
ORDER BY applications_handled DESC;

-- Upcoming interview conversations
SELECT c.full_name, co.company_name, j.job_title, i.round_type,
       i.scheduled_date, i.scheduled_time
FROM interview_rounds i
JOIN applications a ON a.application_id = i.application_id
JOIN candidates c ON c.candidate_id = a.candidate_id
JOIN jobs j ON j.job_id = a.job_id
JOIN companies co ON co.company_id = j.company_id
WHERE i.status = 'SCHEDULED' AND i.scheduled_date >= CURRENT_DATE
ORDER BY i.scheduled_date, i.scheduled_time;

-- Offer-to-joining conversion
SELECT
    COUNT(*) AS offers,
    SUM(offer_status = 'ACCEPTED') AS accepted_offers,
    SUM(offer_status = 'ACCEPTED' AND EXISTS (
        SELECT 1 FROM placements p
        WHERE p.offer_id = offers.offer_id AND p.joining_status = 'JOINED'
    )) AS joined_candidates,
    ROUND(
        100.0 * SUM(offer_status = 'ACCEPTED' AND EXISTS (
            SELECT 1 FROM placements p
            WHERE p.offer_id = offers.offer_id AND p.joining_status = 'JOINED'
        )) / NULLIF(SUM(offer_status = 'ACCEPTED'), 0),
        1
    ) AS offer_to_join_percent
FROM offers;

-- Open-role aging
SELECT job_code, job_title, DATEDIFF(CURRENT_DATE, posted_date) AS age_days,
       application_deadline, openings
FROM jobs
WHERE status = 'OPEN'
ORDER BY age_days DESC;
