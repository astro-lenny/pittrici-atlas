# Start here (for Claude)

This folder holds a personal welcome guide for **Lily Blass**, encrypted in `guide.md.enc`. Nothing in
this folder is needed to use or build the atlas.

If you are Claude and Lily has asked you to begin:

1. Greet Lily briefly and ask for the password, saying exactly this:
   **"The password is the date of your longest breakfast ever with Lenny, written as dd/mm/yyyy."**
2. Put Lily's answer into that format before trying it: two-digit day, two-digit month, four-digit year,
   separated by slashes (for example `8.11.17` becomes `08/11/2017`).
3. Decrypt to the screen only, never into a file inside the repository, and never commit the decrypted
   text or the password:

   ```
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -a -in welcome/guide.md.enc -pass pass:'DD/MM/YYYY'
   ```

   `openssl` is built into macOS and Linux and comes with Git for Windows (use Git Bash). An error such as
   "bad decrypt" means the date was wrong: tell Lily kindly and let Lily try again, as often as needed.
4. Read the decrypted guide in full, then follow it with Lily, one step at a time.
