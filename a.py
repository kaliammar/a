import os, struct, uuid, hashlib, hmac, time
import customtkinter as ctk
from tkinter import filedialog, messagebox

# --- Luxury Colors ---
BG = "#08080A"
CARD = "#141416"
CARD2 = "#1C1C1F"
GOLD = "#D4AF37"
GOLD_H = "#C9A227"
TEXT = "#E8E6E1"

VAULT_DIR = "RoyalVault_Data"
CONFIG_FILE = os.path.join(VAULT_DIR, ".cfg")

ctk.set_appearance_mode("dark")

# --- PURE PYTHON STRONG ENCRYPTION (No external libs) ---
def derive_keys(password: str, salt: bytes):
    master = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000, dklen=64)
    return master[:32], master[32:]  # enc_key, mac_key

def encrypt_blob(enc_key, mac_key, plaintext: bytes) -> bytes:
    nonce = os.urandom(16)
    keystream = b''
    counter = 0
    while len(keystream) < len(plaintext):
        keystream += hmac.new(enc_key, nonce + struct.pack(">Q", counter), hashlib.sha256).digest()
        counter += 1
    keystream = keystream[:len(plaintext)]
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, keystream))
    tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
    return nonce + tag + ciphertext  # 16 + 32 + data

def decrypt_blob(enc_key, mac_key, blob: bytes) -> bytes:
    if len(blob) < 48: raise ValueError("Corrupted")
    nonce, tag, ciphertext = blob[:16], blob[16:48], blob[48:]
    if not hmac.compare_digest(tag, hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()):
        raise ValueError("Wrong password or corrupted")
    keystream = b''
    counter = 0
    while len(keystream) < len(ciphertext):
        keystream += hmac.new(enc_key, nonce + struct.pack(">Q", counter), hashlib.sha256).digest()
        counter += 1
    keystream = keystream[:len(ciphertext)]
    return bytes(a ^ b for a, b in zip(ciphertext, keystream))

def secure_delete(path):
    try:
        size = os.path.getsize(path)
        with open(path, "r+b") as f:
            for _ in range(2):
                f.seek(0); f.write(os.urandom(size))
        os.remove(path)
    except:
        try: os.remove(path)
        except: pass

class RoyalVault(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("ROYAL VAULT")
        self.geometry("1050x680")
        self.configure(fg_color=BG)
        self.enc_key = self.mac_key = None

        self.login = ctk.CTkFrame(self, fg_color=BG)
        self.login.pack(fill="both", expand=True)

        ctk.CTkLabel(self.login, text="👑", font=("Arial", 60)).pack(pady=(80,5))
        ctk.CTkLabel(self.login, text="ROYAL VAULT", font=("Arial Black", 30), text_color=GOLD).pack()
        ctk.CTkLabel(self.login, text="Military-Grade Secret Vault", font=("Arial", 13), text_color="#8A8885").pack(pady=5)

        self.pass_entry = ctk.CTkEntry(self.login, width=340, height=50, placeholder_text="Master Password", show="•", corner_radius=14, fg_color=CARD, border_color=GOLD, font=("Arial", 14))
        self.pass_entry.pack(pady=25)
        self.pass_entry.bind("<Return>", lambda e: self.unlock())

        ctk.CTkButton(self.login, text="UNLOCK VAULT", width=340, height=48, corner_radius=14, fg_color=GOLD, hover_color=GOLD_H, text_color="black", font=("Arial Black", 14), command=self.unlock).pack()
        self.msg = ctk.CTkLabel(self.login, text="", text_color="#FF5555")
        self.msg.pack(pady=12)

        if not os.path.exists(VAULT_DIR): os.makedirs(VAULT_DIR)
        if not os.path.exists(CONFIG_FILE):
            self.msg.configure(text="First time? Set a strong password", text_color=GOLD)

    def unlock(self):
        pwd = self.pass_entry.get()
        if len(pwd) < 6:
            self.msg.configure(text="Password must be 6+ chars"); return
        try:
            if not os.path.exists(CONFIG_FILE):
                salt = os.urandom(32)
                ek, mk = derive_keys(pwd, salt)
                verifier = encrypt_blob(ek, mk, b"ROYAL_VAULT_VERIFIED")
                open(CONFIG_FILE, "wb").write(salt + b"::" + verifier)
            else:
                raw = open(CONFIG_FILE, "rb").read()
                salt, verifier = raw.split(b"::")
                ek, mk = derive_keys(pwd, salt)
                if decrypt_blob(ek, mk, verifier) != b"ROYAL_VAULT_VERIFIED": raise ValueError()
            self.enc_key, self.mac_key = ek, mk
            self.show_main()
        except Exception:
            self.msg.configure(text="Wrong password!")

    def show_main(self):
        self.login.destroy()
        top = ctk.CTkFrame(self, fg_color=CARD, height=65, corner_radius=0)
        top.pack(fill="x")
        ctk.CTkLabel(top, text="ROYAL VAULT  |  Encrypted Files", font=("Arial Black", 16), text_color=GOLD).pack(side="left", padx=20, pady=15)
        
        act = ctk.CTkFrame(self, fg_color=BG)
        act.pack(fill="x", padx=20, pady=12)
        ctk.CTkButton(act, text="+ Add Files", fg_color=GOLD, text_color="black", hover_color=GOLD_H, corner_radius=12, height=40, command=self.add_files).pack(side="left", padx=5)
        ctk.CTkButton(act, text="Add Folder", fg_color=CARD, hover_color=CARD2, border_color=GOLD, border_width=1, corner_radius=12, height=40, command=self.add_folder).pack(side="left", padx=5)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=BG)
        self.scroll.pack(fill="both", expand=True, padx=15, pady=10)
        self.refresh()

    def refresh(self):
        for w in self.scroll.winfo_children(): w.destroy()
        files = []
        for name in os.listdir(VAULT_DIR):
            if name.endswith(".vault"):
                try:
                    blob = open(os.path.join(VAULT_DIR, name), "rb").read()
                    plain = decrypt_blob(self.enc_key, self.mac_key, blob)
                    l = struct.unpack(">I", plain[:4])[0]
                    fname = plain[4:4+l].decode()
                    files.append((name, fname, len(plain)-4-l))
                except: pass
        if not files:
            ctk.CTkLabel(self.scroll, text="Vault is empty - Add your secret files here", text_color="#666", font=("Arial", 15)).pack(pady=100)
            return
        for enc, real, size in files:
            row = ctk.CTkFrame(self.scroll, fg_color=CARD, corner_radius=14)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text="🔐", font=("Arial", 20)).pack(side="left", padx=12)
            ctk.CTkLabel(row, text=real, font=("Arial Bold", 12), width=380, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"{size/1024:.1f} KB", text_color="#888").pack(side="left", padx=10)
            ctk.CTkButton(row, text="Decrypt", width=75, height=32, fg_color=GOLD, text_color="black", corner_radius=8, command=lambda n=enc: self.decrypt_one(n)).pack(side="right", padx=5)
            ctk.CTkButton(row, text="Delete", width=65, height=32, fg_color="#2A1A1A", hover_color="#FF3333", corner_radius=8, command=lambda n=enc: self.delete_one(n)).pack(side="right", padx=10, pady=8)

    def encrypt_file(self, path):
        with open(path, "rb") as f: data = f.read()
        fname = os.path.basename(path).encode()
        packed = struct.pack(">I", len(fname)) + fname + data
        blob = encrypt_blob(self.enc_key, self.mac_key, packed)
        open(os.path.join(VAULT_DIR, uuid.uuid4().hex + ".vault"), "wb").write(blob)
        secure_delete(path)

    def add_files(self):
        for p in filedialog.askopenfilenames(): self.encrypt_file(p)
        self.refresh()
    def add_folder(self):
        d = filedialog.askdirectory()
        if not d: return
        for r, _, fs in os.walk(d):
            for f in fs: self.encrypt_file(os.path.join(r, f))
        self.refresh()
    def decrypt_one(self, enc):
        out = filedialog.askdirectory()
        if not out: return
        blob = open(os.path.join(VAULT_DIR, enc), "rb").read()
        plain = decrypt_blob(self.enc_key, self.mac_key, blob)
        l = struct.unpack(">I", plain[:4])[0]
        fname = plain[4:4+l].decode()
        open(os.path.join(out, fname), "wb").write(plain[4+l:])
        messagebox.showinfo("Done", f"Decrypted: {fname}")
    def delete_one(self, enc):
        os.remove(os.path.join(VAULT_DIR, enc)); self.refresh()

if __name__ == "__main__":
    app = RoyalVault()
    app.mainloop()
