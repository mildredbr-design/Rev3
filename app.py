
import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Simulador Revolving", layout="wide")
st.title("💳 Simulador de Préstamo Revolving - Método Francés con Opciones de Cuota")

# ---------------- FUNCIONES ----------------
def simulador(capital, interes, meses, cuota_opcional):
    saldo = capital
    i = interes / 12 / 100
    cuota = cuota_opcional
    datos = []

    for mes in range(1, meses + 1):
        interes_mes = saldo * i
        cuota_actual = cuota

        # Ajustar la última cuota si es mayor que el saldo restante
        if saldo < cuota - interes_mes:
            cuota_actual = saldo + interes_mes
            saldo = 0
        else:
            saldo -= (cuota - interes_mes)

        datos.append({
            "Mes": mes,
            "Cuota": round(cuota_actual, 2),
            "Intereses": round(interes_mes, 2),
            "Saldo": round(saldo, 2)
        })

        if saldo <= 0:
            break

    return pd.DataFrame(datos)

# ---------------- INPUTS ----------------
capital = st.number_input("Capital inicial (€)", 0.0,
