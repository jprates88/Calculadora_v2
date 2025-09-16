import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
from datetime import datetime

st.set_page_config(page_title="Estimativa Azure", layout="centered")

st.title("📊 Estimativa de Custos Azure via MeterId")
st.write("Faça o upload da planilha com os MeterIds e quantidades para obter uma estimativa de custo usando a Azure Retail API.")

uploaded_file = st.file_uploader("📁 Envie um arquivo .xlsx com colunas 'MeterId' e 'Quantity'", type="xlsx")

# Função de busca na Azure API
@st.cache_data(show_spinner=False)
def buscar_detalhes_por_meter_id(meter_id, regioes):
    for regiao in regioes:
        url = f"https://prices.azure.com/api/retail/prices?$filter=meterId eq '{meter_id}' and armRegionName eq '{regiao}'"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                items = response.json().get("Items", [])
                if items:
                    item = items[0]
                    return {
                        "unitPrice": float(item.get("unitPrice", 0.0)),
                        "skuName": item.get("skuName", ""),
                        "serviceName": item.get("serviceName", ""),
                        "armRegionName": item.get("armRegionName", "")
                    }
        except:
            pass
    return None

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    if "MeterId" not in df.columns or "Quantity" not in df.columns:
        st.error("❌ A planilha deve conter as colunas 'MeterId' e 'Quantity'.")
        st.stop()

    regioes_preferidas = ["brazilsouth", "eastus2", "Global", "Intercontinental", "Zone 1", "Zone 3"]

    # Colunas para preencher
    precos_unitarios = []
    precos_finais = []
    sku_names = []
    service_names = []
    azure_regions = []

    total = len(df)

    progresso = st.progress(0, text="Iniciando...")

    meter_id_cache = {}

    for i, row in df.iterrows():
        meter_id = str(row["MeterId"]).strip()
        quantidade = float(row["Quantity"])

        if meter_id in meter_id_cache:
            dados = meter_id_cache[meter_id]
        else:
            dados = buscar_detalhes_por_meter_id(meter_id, regioes_preferidas)
            meter_id_cache[meter_id] = dados

        if dados:
            preco_unitario = dados["unitPrice"]
            sku_name = dados["skuName"]
            service_name = dados["serviceName"]
            regiao = dados["armRegionName"]

            # Ajuste de preço unitário baseado na descrição do SKU
            sku_name_lower = sku_name.lower()

            if "100 tb" in sku_name_lower:
                preco_unitario /= 102400  # Convertendo para preço por GB
            elif "1 tb" in sku_name_lower:
                preco_unitario /= 1024  # Convertendo para preço por GB
            elif "per gb" in sku_name_lower or "1 gb" in sku_name_lower:
                pass  # Já está por GB
            elif "per 10k transactions" in sku_name_lower:
                preco_unitario /= 10000  # Convertendo para preço por transação
            elif "per hour" in sku_name_lower:
                pass  # Já está por hora
            elif "per 100 units" in sku_name_lower:
                preco_unitario /= 100  # Convertendo para preço por unidade

            preco_final = preco_unitario * quantidade

            precos_unitarios.append(round(preco_unitario, 6))
            precos_finais.append(round(preco_final, 4))
            sku_names.append(sku_name)
            service_names.append(service_name)
            azure_regions.append(regiao)
        else:
            precos_unitarios.append(None)
            precos_finais.append(None)
            sku_names.append(None)
            service_names.append(None)
            azure_regions.append(None)

        progresso.progress((i + 1) / total, text=f"Processando linha {i+1} de {total} ({int((i+1)/total*100)}%)")
        time.sleep(0.05)  # Reduzido para acelerar sem sobrecarregar a API

    df["Custo_Unitario_USD"] = precos_unitarios
    df["Preco_Final_USD"] = precos_finais
    df["SKU_Name"] = sku_names
    df["Service_Name"] = service_names
    df["Azure_Region"] = azure_regions

    # Gera arquivo de saída
    buffer = BytesIO()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo = f"Estimativa_Azure_{timestamp}.xlsx"
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    st.success("✅ Processamento concluído!")
    st.download_button(
        label="📥 Baixar planilha com estimativas",
        data=buffer,
        file_name=nome_arquivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
