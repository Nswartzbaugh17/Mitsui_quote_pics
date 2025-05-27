import streamlit as st
from fpdf import FPDF
import json
import os
import re
from collections import defaultdict

# Load configuration
with open("all_machine_configs.json") as f:
    machine_configs = json.load(f)

os.makedirs("option_images", exist_ok=True)
os.makedirs("machine_images", exist_ok=True)

# Helpers
def clean_standard_options(options):
    cleaned = []
    for opt in options:
        text = str(opt).replace("nan", "").strip()
        if text:
            cleaned.append(text)
    return cleaned

def group_optional_options(options):
    categories = defaultdict(list)
    cleaned_options = []

    for opt in options:
        desc = re.sub(r'\bnan\b', '', str(opt.get("description", ""))).strip()
        opt['description'] = desc
        if desc:
            cleaned_options.append(opt)

    base_price = 0
    if cleaned_options and (
        "base price" in cleaned_options[0]['description'].lower()
        or "model" in cleaned_options[0]['description'].lower()
        or (cleaned_options[0]['price'] > 100000 and len(cleaned_options[0]['description'].split()) < 3)
    ):
        base_price = cleaned_options[0]['price']
        cleaned_options = cleaned_options[1:]

    for opt in cleaned_options:
        desc = opt['description'].lower()
        if 'spindle' in desc:
            categories['Spindle Options'].append(opt)
        elif 'probe' in desc or 'renishaw' in desc:
            categories['Probing & Measurement'].append(opt)
        elif 'coolant' in desc:
            categories['Coolant Systems'].append(opt)
        elif 'table' in desc or 'pallet' in desc:
            categories['Table & Pallet Systems'].append(opt)
        elif 'tool' in desc and ('storage' in desc or 'magazine' in desc or 'changer' in desc):
            categories['Tool Storage'].append(opt)
        elif 'control' in desc:
            categories['Control Options'].append(opt)
        else:
            categories['Other Options'].append(opt)

    return categories, base_price

# PDF class
class QuotePDF(FPDF):
    def header(self):
        self.image("mitsui_logo.png", x=10, y=8, w=45)
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Mitsui Seiki USA - Machine Quote', ln=True, align='C')
        self.ln(15)

    def add_quote(self, customer_name, machine_type, base_price, discount, std_opts, selected_opts, total):
        self.set_font("Arial", size=12)
        self.cell(0, 10, f"Customer: {customer_name}", ln=True)
        self.cell(0, 10, f"Machine: {machine_type}", ln=True)
        self.cell(0, 10, f"Base Machine Price: ${base_price:,.2f}", ln=True)
        self.cell(0, 10, f"Standard Discount: -${discount:,.2f}", ln=True)
        self.ln(5)

        # Embed machine image
        image_path = f"machine_images/{machine_type}.jpg"
        if os.path.exists(image_path):
            try:
                self.image(image_path, x=80, w=120)
                self.ln(10)
            except:
                self.cell(0, 10, "[Could not load machine image]", ln=True)

        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "Standard Options:", ln=True)
        self.set_font("Arial", size=12)
        for opt in std_opts:
            self.multi_cell(0, 10, f"- {opt}")
        self.ln(5)

        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, "Selected Optional Upgrades:", ln=True)
        self.set_font("Arial", size=12)
        grouped, _ = group_optional_options(selected_opts)
        for group, items in grouped.items():
            self.set_font("Arial", 'B', 11)
            self.cell(0, 10, f"{group}:", ln=True)
            self.set_font("Arial", size=12)
            for opt in items:
                desc = opt['description']
                price = opt['price']
                self.multi_cell(0, 10, f"- {desc} (${price:,.2f})")
                code = opt.get("code")
                if code:
                    img_path = f"option_images/{code}.jpg"
                    if os.path.exists(img_path):
                        try:
                            self.image(img_path, x=self.get_x()+5, w=60)
                            self.ln(5)
                        except Exception as e:
                            self.cell(0, 10, f"[Image Error: {e}]", ln=True)
                self.ln(3)

        self.ln(5)
        self.set_font("Arial", 'B', 12)
        self.cell(0, 10, f"Total Quote: ${total:,.2f}", ln=True)

# Streamlit UI
st.set_page_config(page_title="Quote Builder", layout="centered")
st.title("Mitsui Seiki - Quote Builder")

customer_name = st.text_input("Customer Name")
machine_type = st.selectbox("Select Machine Type", sorted(machine_configs.keys()))

standard_options = clean_standard_options(machine_configs[machine_type]['standard_options'])
optional_options = machine_configs[machine_type]['optional_options']

grouped_options, extracted_base_price = group_optional_options(optional_options)
base_price = extracted_base_price if extracted_base_price > 0 else machine_configs[machine_type]['base_price']

# Show machine image
machine_image_path = f"machine_images/{machine_type}.jpg"
if os.path.exists(machine_image_path):
    st.image(machine_image_path, caption=machine_type, width=400)

st.subheader("Discount Options")
with st.expander("Apply Discount"):
    desired_price = st.number_input("Enter Desired Final Price (Optional)", min_value=0.0, format="%.2f")
    percent_discount = st.number_input("Discount Percentage (%)", min_value=0.0, max_value=100.0, format="%.2f")
    flat_discount = st.number_input("Flat Discount Amount ($)", min_value=0.0, format="%.2f")

if desired_price > 0:
    discount = max(0, base_price - desired_price)
elif percent_discount > 0:
    discount = (percent_discount / 100) * base_price
elif flat_discount > 0:
    discount = flat_discount
else:
    discount = machine_configs[machine_type]['discount']

custom_price = base_price - discount

st.subheader("Standard Features (Included)")
for item in standard_options:
    st.markdown(f"- {item}")

st.subheader("Optional Upgrades")
selected_addons = []
for group, options in grouped_options.items():
    st.markdown(f"**{group}**")
    for i, opt in enumerate(options):
        key = f"{machine_type}_{group}_{i}"
        code = opt.get("code", f"{group}_{i}")

        if st.checkbox(f"{opt['description']} (+${opt['price']:,.2f})", key=key):
            selected_addons.append(opt)
            custom_price += opt['price']

        image_path = f"option_images/{code}.jpg"
        if os.path.exists(image_path):
            st.image(image_path, caption="Saved Image", width=150)

        image_file = st.file_uploader(f"Upload image for {code}", type=["jpg", "png"], key=f"upload_{machine_type}_{group}_{i}")
        if image_file:
            with open(image_path, "wb") as f:
                f.write(image_file.getbuffer())
            st.success(f"Image saved for {code}")

if st.button("Generate Quote PDF"):
    pdf = QuotePDF()
    pdf.add_page()
    pdf.add_quote(customer_name or "[Customer Name]", machine_type, base_price, discount, standard_options, selected_addons, custom_price)
    pdf_output_path = "quote_output.pdf"
    pdf.output(pdf_output_path)
    st.success("Quote generated successfully!")
    st.download_button("Download Quote PDF", open(pdf_output_path, "rb"), file_name="Mitsui_Quote.pdf")
