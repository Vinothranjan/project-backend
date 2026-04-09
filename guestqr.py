import qrcode
import os

def generate_guest_qr():
    # Ask for Guest's Name
    guest_name = input("Enter Guest Name: ").strip()
    
    if not guest_name:
        print("Error: Name cannot be empty.")
        return
    
    # Format the data
    qr_data = f"GUEST:{guest_name}"
    
    # Create QR object
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create the Image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Filename
    filename = f"guest_qr_{guest_name.lower().replace(' ', '_')}.png"
    
    # Save the file
    img.save(filename)
    
    print(f"Success! Guest QR Code generated for {guest_name}.")
    print(f"Saved as: {filename}")
    print(f"Full path: {os.path.abspath(filename)}")

if __name__ == "__main__":
    generate_guest_qr()
