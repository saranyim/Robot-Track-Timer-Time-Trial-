import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports

class RobotTimerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Time Trial - Track Timer")
        self.root.geometry("650x450")
        self.root.resizable(False, False)
        
        self.ser = None
        self.is_running = False
        self.read_thread = None

        # สไตล์หน้าจอแนว Modern / Dark Mode
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # ส่วนแสดงผลสถานะและการเชื่อมต่อ
        self.conn_frame = ttk.LabelFrame(root, text=" การเชื่อมต่อบอร์ด Arduino ", padding=10)
        self.conn_frame.pack(fill="x", padx=20, pady=10)
        
        self.port_label = ttk.Label(self.conn_frame, text="พอร์ต:")
        self.port_label.pack(side="left", padx=5)
        
        self.port_combobox = ttk.Combobox(self.conn_frame, width=35, state="readonly")
        self.port_combobox.pack(side="left", padx=5)
        
        self.refresh_btn = ttk.Button(self.conn_frame, text="รีเฟรช", command=self.refresh_ports)
        self.refresh_btn.pack(side="left", padx=5)
        
        self.connect_btn = ttk.Button(self.conn_frame, text="เชื่อมต่อ", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=5)

        # ส่วนแสดงค่าสถานะ และตัวเลขนับเวลา
        self.display_frame = tk.Frame(root, bg="#1e1e1e", bd=2, relief="sunken")
        self.display_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.status_label = tk.Label(self.display_frame, text="DISCONNECTED", font=("Helvetica", 16, "bold"), fg="#ff4757", bg="#1e1e1e")
        self.status_label.pack(pady=15)
        
        self.time_label = tk.Label(self.display_frame, text="0.000000", font=("Courier New", 55, "bold"), fg="#2ed573", bg="#1e1e1e")
        self.time_label.pack(pady=10)
        
        self.unit_label = tk.Label(self.display_frame, text="วินาที (Seconds)", font=("Helvetica", 12), fg="#a4b0be", bg="#1e1e1e")
        self.unit_label.pack()

        # ปุ่มควบคุมระบบ
        self.control_frame = tk.Frame(root)
        self.control_frame.pack(fill="x", padx=20, pady=15)
        
        # แก้ไขเอา height=2 ออกจาก pack() และใส่ในโครงสร้างปุ่มอย่างถูกต้องแล้วครับ
        self.reset_btn = tk.Button(self.control_frame, text="RESET SYSTEM / START NEW RUN", font=("Helvetica", 14, "bold"), bg="#ffa502", fg="white", activebackground="#eccc68", command=self.send_reset, state="disabled", height=2)
        self.reset_btn.pack(fill="x")

        self.refresh_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combobox['values'] = port_list
        if port_list:
            self.port_combobox.current(0)
            
    def toggle_connection(self):
        if self.ser and self.ser.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        selected_port = self.port_combobox.get()
        if not selected_port:
            messagebox.showwarning("ข้อผิดพลาด", "กรุณาเลือกพอร์ต Arduino")
            return
        
        try:
            self.ser = serial.Serial(selected_port, 115200, timeout=1)
            time.sleep(2) # รอ Auto-Reset ของบอร์ด
            
            self.is_running = True
            self.connect_btn.config(text="ตัดการเชื่อมต่อ")
            self.port_combobox.config(state="disabled")
            self.refresh_btn.config(state="disabled")
            self.reset_btn.config(state="normal")
            
            self.read_thread = threading.Thread(target=self.read_serial_data, daemon=True)
            self.read_thread.start()
            
            self.update_status("READY / WAITING", "#5352ed")
        except Exception as e:
            messagebox.showerror("เชื่อมต่อล้มเหลว", f"ไม่สามารถเปิดพอร์ตได้: {e}")

    def disconnect_serial(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        
        self.connect_btn.config(text="เชื่อมต่อ")
        self.port_combobox.config(state="readonly")
        self.refresh_btn.config(state="normal")
        self.reset_btn.config(state="disabled")
        self.update_status("DISCONNECTED", "#ff4757")

    def read_serial_data(self):
        while self.is_running:
            if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8').strip()
                    if not line:
                        continue
                    
                    if line == "STATUS:READY":
                        self.update_status("READY / WAITING", "#2ed573")
                    elif line.startswith("RUN:"):
                        # แก้ไขดึงค่าอาร์เรย์ตัวเลขตำแหน่งที่ 1 และฟอร์แมตทศนิยมเรียบร้อยครับ
                        parts = line.split(":")
                        if len(parts) > 1:
                            formatted_time = f"{float(parts[1]):.6f}"
                            self.update_time_display(formatted_time)
                            self.update_status("ROBOT RUNNING...", "#ffa502")
                    elif line.startswith("TIME:"):
                        # แก้ไขดึงค่าเวลาสรุปรอบสุดท้ายตำแหน่งที่ 1 เรียบร้อยครับ
                        parts = line.split(":")
                        if len(parts) > 1:
                            self.update_time_display(parts[1])
                            self.update_status("FINISH! SUCCESS", "#2ed573")
                except Exception as e:
                    print(f"Read error: {e}")
                    break
            time.sleep(0.005)

    def send_reset(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"RESET\n")
                self.time_label.config(text="0.000000")
                self.update_status("READY / WAITING", "#2ed573")
            except Exception as e:
                print(f"Error sending reset: {e}")

    def update_status(self, text, color):
        self.root.after(0, lambda: self.status_label.config(text=text, fg=color))

    def update_time_display(self, time_str):
        self.root.after(0, lambda: self.time_label.config(text=time_str))

    def on_closing(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotTimerGUI(root)
    root.mainloop()
