import streamlit as st
import pandas as pd
from PIL import Image
from io import BytesIO
import numpy as np
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from streamlit_drawable_canvas import st_canvas

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema de Recepción de Materiales", layout="wide")

# --- USUARIOS Y CLAVES ---
USUARIOS = {
    "admin": {"clave": "1234", "rol": "Administrador"},
    "supervisor": {"clave": "5678", "rol": "Supervisor"}
}

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_actual" not in st.session_state:
    st.session_state.usuario_actual = ""
if "rol_actual" not in st.session_state:
    st.session_state.rol_actual = ""

# --- ALMACENAMIENTO DE SOLICITUDES EN MEMORIA ---
if 'solicitudes' not in st.session_state:
    st.session_state.solicitudes = {}

# --- PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.title("🔒 Acceso Restringido - Recepción de Materiales")
    col1, _ = st.columns([1, 2])
    with col1:
        user_input = st.text_input("Usuario")
        pass_input = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión"):
            user_clean = user_input.strip().lower()
            if user_clean in USUARIOS and USUARIOS[user_clean]["clave"] == pass_input:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = user_clean
                st.session_state.rol_actual = USUARIOS[user_clean]["rol"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.write(f"👤 Conectado como: **{st.session_state.rol_actual}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario_actual = ""
    st.session_state.rol_actual = ""
    st.rerun()

st.title("📦 Sistema de Recepción y Verificación de Materiales")

# --- MÓDULO DE CARGA (SOLO ADMINISTRADOR) ---
if st.session_state.rol_actual == "Administrador":
    st.subheader("⚙️ Cargar Nueva Solicitud")
    col_num, col_file = st.columns([1, 2])
    
    with col_num:
        nuevo_num_solicitud = st.text_input("Número de Solicitud / Proyecto:", "1001")
        
    with col_file:
        uploaded_file = st.file_uploader("Cargar lista de materiales (Excel o CSV)", type=["xlsx", "csv"])

    if st.button("Guardar y Publicar Solicitud"):
        if uploaded_file is not None and nuevo_num_solicitud:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    try:
                        df_temp = pd.read_excel(uploaded_file, sheet_name=1, header=None)
                        hoja_usada = 1
                    except Exception:
                        df_temp = pd.read_excel(uploaded_file, sheet_name=0, header=None)
                        hoja_usada = 0

                    header_row = 0
                    for idx, row in df_temp.iterrows():
                        row_values = row.astype(str).str.lower().tolist()
                        if any(k in row_values for k in ['item', 'descripción', 'descripcion', 'unidad', 'cantidad', 'oc', 'nv']):
                            header_row = idx
                            break

                    df = pd.read_excel(uploaded_file, sheet_name=hoja_usada, header=header_row)

                # Limpieza de columnas completamente vacías
                df = df.dropna(how='all').dropna(how='all', axis=1)
                
                # Eliminar columnas sin nombre por defecto
                df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed')]

                if 'Verificado' not in df.columns:
                    df['Verificado'] = False
                if 'Observaciones' not in df.columns:
                    df['Observaciones'] = ""

                st.session_state.solicitudes[nuevo_num_solicitud] = {
                    "data": df
                }
                st.success(f"✅ Solicitud N°{nuevo_num_solicitud} guardada correctamente.")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")
        else:
            st.warning("Debe ingresar un número de solicitud y adjuntar un archivo.")

st.divider()

# --- MÓDULO DE SELECCIÓN Y GESTIÓN DE SOLICITUDES ---
st.subheader("📋 Solicitudes Disponibles")

lista_solicitudes = list(st.session_state.solicitudes.keys())

if not lista_solicitudes:
    st.info("ℹ️ No hay solicitudes registradas en el sistema. Un Administrador debe cargar una nueva solicitud.")
else:
    solicitud_seleccionada = st.selectbox(
        "Seleccione la solicitud que desea revisar / verificar:",
        options=lista_solicitudes
    )

    if solicitud_seleccionada:
        datos_solicitud = st.session_state.solicitudes[solicitud_seleccionada]
        df_actual = datos_solicitud["data"]

        st.markdown(f"### 📂 Materiales de la Solicitud N° {solicitud_seleccionada}")

        # Tabla editable
        edited_df = st.data_editor(
            df_actual,
            column_config={
                "Verificado": st.column_config.CheckboxColumn("Recibido OK", default=False),
                "Observaciones": st.column_config.TextColumn("Observaciones", default="")
            },
            disabled=[col for col in df_actual.columns if col not in ['Verificado', 'Observaciones']],
            use_container_width=True,
            hide_index=True,
            key=f"editor_{solicitud_seleccionada}"
        )

        st.session_state.solicitudes[solicitud_seleccionada]["data"] = edited_df

        # Avance de verificación
        total_items = len(edited_df)
        items_verificados = edited_df['Verificado'].sum() if 'Verificado' in edited_df.columns else 0
        porcentaje = int((items_verificados / total_items) * 100) if total_items > 0 else 0

        st.progress(porcentaje / 100)
        st.caption(f"Avance de verificación: {porcentaje}% ({items_verificados}/{total_items} ítems)")

        if porcentaje == 100:
            st.success(f"🎉 ¡SOLICITUD N° {solicitud_seleccionada} COMPLETADA AL 100%! Todos los materiales han sido verificados.")

        # --- EVIDENCIA Y FIRMAS ---
        st.divider()
        st.markdown(f"#### ✍️ Evidencia y Firmas - Solicitud N° {solicitud_seleccionada}")
        col_cam, col_fir1, col_fir2 = st.columns(3)

        with col_cam:
            st.write("**Fotografía de Respaldo**")
            foto = st.camera_input("Tomar foto del material", key=f"cam_{solicitud_seleccionada}")

        with col_fir1:
            st.write("**Firma Supervisor / Revisor**")
            canvas_rev = st_canvas(
                stroke_width=2, stroke_color="#000000", background_color="#FFFFFF",
                height=150, width=230, key=f"canvas_rev_{solicitud_seleccionada}"
            )

        with col_fir2:
            st.write("**Firma Entrega / Bodega**")
            canvas_bod = st_canvas(
                stroke_width=2, stroke_color="#000000", background_color="#FFFFFF",
                height=150, width=230, key=f"canvas_bod_{solicitud_seleccionada}"
            )

        # --- GENERACIÓN DE REPORTE PDF ---
        st.divider()
        if st.button("📄 Generar Reporte PDF", key=f"pdf_{solicitud_seleccionada}"):
            buffer = BytesIO()
            # Formato apaisado (landscape) para acomodar todas las columnas de Excel adecuadamente
            doc = SimpleDocTemplate(
                buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25
            )
            story = []
            styles = getSampleStyleSheet()

            # Título principal
            title_style = ParagraphStyle(
                'TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20,
                textColor=colors.HexColor("#003366"), alignment=1
            )
            story.append(Paragraph(f"REPORTE DE RECEPCIÓN DE MATERIALES - SOLICITUD N° {solicitud_seleccionada}", title_style))
            story.append(Spacer(1, 15))

            # Estilos de celdas
            header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=10, fontName="Helvetica-Bold", textColor=colors.whitesmoke, alignment=1)
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, fontName="Helvetica", alignment=1)

            # Preparación de columnas
            cols_df = list(edited_df.columns)
            
            # Encabezados de la tabla
            header_row = [Paragraph(str(c), header_style) for c in cols_df]
            tabla_data = [header_row]

            # Filas de datos
            for _, row in edited_df.iterrows():
                row_cells = []
                for col_name in cols_df:
                    val = row[col_name]
                    if col_name == "Verificado":
                        text_val = "OK" if val else "PENDIENTE"
                    elif pd.isna(val):
                        text_val = ""
                    else:
                        text_val = str(val)
                    row_cells.append(Paragraph(text_val, cell_style))
                tabla_data.append(row_cells)

            # Ancho disponible en paisaje: ~750pt
            num_cols = len(cols_df)
            col_width = 750 / num_cols if num_cols > 0 else 750
            
            t = Table(tabla_data, colWidths=[col_width] * num_cols)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(t)
            story.append(Spacer(1, 25))

            # --- EXTRACCIÓN SEGURA DE IMÁGENES Y FIRMAS ---
            img_foto, img_rev, img_bod = None, None, None

            # Foto
            if foto is not None:
                try:
                    img_f = Image.open(foto)
                    f_buffer = BytesIO()
                    img_f.save(f_buffer, format='PNG')
                    f_buffer.seek(0)
                    img_foto = RLImage(f_buffer, width=160, height=100)
                except Exception:
                    pass

            # Firma Supervisor
            try:
                if canvas_rev is not None and canvas_rev.image_data is not None:
                    arr_rev = canvas_rev.image_data.astype('uint8')
                    if np.any(arr_rev[:, :, 3] > 0): # Verificar si contiene trazos dibujados
                        img_r = Image.fromarray(arr_rev)
                        r_buffer = BytesIO()
                        img_r.save(r_buffer, format='PNG')
                        r_buffer.seek(0)
                        img_rev = RLImage(r_buffer, width=160, height=80)
            except Exception:
                pass

            # Firma Bodega
            try:
                if canvas_bod is not None and canvas_bod.image_data is not None:
                    arr_bod = canvas_bod.image_data.astype('uint8')
                    if np.any(arr_bod[:, :, 3] > 0): # Verificar si contiene trazos dibujados
                        img_b = Image.fromarray(arr_bod)
                        b_buffer = BytesIO()
                        img_b.save(b_buffer, format='PNG')
                        b_buffer.seek(0)
                        img_bod = RLImage(b_buffer, width=160, height=80)
            except Exception:
                pass

            # Generar Cuadro de Evidencia y Firmas al Final
            lbl_style = ParagraphStyle('LblStyle', parent=styles['Normal'], fontSize=9, leading=11, fontName="Helvetica-Bold", alignment=1)
            
            firma_titles = [
                Paragraph("<b>Fotografía de Respaldo</b>", lbl_style),
                Paragraph("<b>Firma Supervisor / Revisor</b>", lbl_style),
                Paragraph("<b>Firma Entrega / Bodega</b>", lbl_style)
            ]
            firma_images = [
                img_foto if img_foto else Paragraph("<i>Sin foto adjunta</i>", cell_style),
                img_rev if img_rev else Paragraph("<i>Sin firma</i>", cell_style),
                img_bod if img_bod else Paragraph("<i>Sin firma</i>", cell_style)
            ]

            tabla_firmas = Table([firma_titles, firma_images], colWidths=[240, 240, 240])
            tabla_firmas.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#F0F2F6"))
            ]))

            story.append(tabla_firmas)

            # Construir el PDF
            doc.build(story)
            buffer.seek(0)

            st.download_button(
                label="⬇️ Descargar PDF de Recepción Completo",
                data=buffer,
                file_name=f"Recepcion_Solicitud_{solicitud_seleccionada}.pdf",
                mime="application/pdf"
            )
