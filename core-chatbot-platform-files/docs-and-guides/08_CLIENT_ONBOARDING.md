# 08 — Client Onboarding (η τυποποιημένη ροή)

Χρόνος-στόχος: λεπτά έως 1 ώρα. Κανένα deploy, κανένα debugging.

1. **Ερωτηματολόγιο**: ο πελάτης συμπληρώνει το Excel (+ συμπληρωματικές ερωτήσεις).
2. **Ματιά στο site του**: χρώματα, λογότυπο, ύφος + λίστα URLs με έγκυρο περιεχόμενο.
3. **JSON**: μεταφέρεις τις απαντήσεις σε JSON (πρότυπο: `05-onboarding/demo_client_komotirio.json`). Το system_prompt φτιάχνεται αυτόματα ή το γράφεις εσύ.
4. **Seed**: `python seed_new_client.py <πελάτης>.json`
5. **Ingestion**: `python ingest_content.py --client <id> --url ... --pdf ... --file ...`
   - Βάλε τα σταθερά URLs του και στο `crawl_urls` του JSON → αυτόματη ανανέωση από το Cron Job.
6. **Δοκιμή**: `/demo?client_id=<id>` — τρέξε τη λίστα του 06_TESTING_STRATEGY.
7. **Παράδοση**: στέλνεις το snippet (`04-widget/embedded_code_sample.html`) με το client_id του + οδηγίες εγκατάστασης για το CMS του (ερωτ. 4.1-4.2).
8. **Follow-up σε 1 εβδομάδα**: κοίτα τα is_unanswered → συμπλήρωσε τη γνώση που λείπει.
