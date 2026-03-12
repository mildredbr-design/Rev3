import streamlit as st
import pandas as pd
from datetime import date, datetime
import calendar
from decimal import Decimal, ROUND_HALF_UP, getcontext
from io import BytesIO

getcontext().prec = 10

st.set_page_config(page_title="Simulador Revolving", layout="wide")
st.title("💳 Simulador Revolving con Amortizaciones Anticipadas")

# ---------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------

def dias_ano(fecha):
    return 366 if calendar.isleap(fecha.year) else 365


def crear_fecha_recibo(fecha_base, dia):
    ultimo_dia = calendar.monthrange(fecha_base.year, fecha_base.month)[1]
    if dia > ultimo_dia:
        dia = ultimo_dia
    return date(fecha_base.year, fecha_base.month, dia)


def siguiente_mes(fecha):
    if fecha.month == 12:
        return date(fecha.year + 1, 1, fecha.day)
    return date(fecha.year, fecha.month + 1, fecha.day)


# ---------------------------------------------------------
# INTERES NORMAL
# ---------------------------------------------------------

def interes_periodo(capital, tin, fecha_inicio, fecha_fin):

    capital = Decimal(str(capital))
    tin = Decimal(str(tin)) / Decimal("100")

    dias = (fecha_fin - fecha_inicio).days
    base = dias_ano(fecha_inicio)

    interes = capital * tin * Decimal(dias) / Decimal(base)

    return interes.quantize(Decimal("0.00001"))


# ---------------------------------------------------------
# INTERES CON AMORTIZACIONES
# ---------------------------------------------------------

def interes_con_amortizaciones(capital, tin, fecha_inicio, fecha_fin, amortizaciones):

    capital = Decimal(str(capital))
    tin = Decimal(str(tin)) / Decimal("100")

    base = dias_ano(fecha_inicio)

    interes_total = Decimal("0")
    fecha_actual = fecha_inicio

    for fecha_amort, importe in amortizaciones:

        dias = (fecha_amort - fecha_actual).days

        interes = capital * tin * Decimal(dias) / Decimal(base)
        interes_total += interes

        capital -= Decimal(str(importe))

        if capital < 0:
            capital = Decimal("0")

        fecha_actual = fecha_amort

    dias_final = (fecha_fin - fecha_actual).days

    interes_final = capital * tin * Decimal(dias_final) / Decimal(base)

    interes_total += interes_final

    return interes_total.quantize(Decimal("0.00001")), capital


# ---------------------------------------------------------
# SIMULADOR
# ---------------------------------------------------------

def simulador(capital, tin, tipo_calculo, valor, fecha_inicio,
              dia_recibo, df_amort, seguro_tasa):

    capital = Decimal(str(capital))
    saldo = capital
    seguro_tasa = Decimal(str(seguro_tasa))

    fecha_pago = crear_fecha_recibo(fecha_inicio, dia_recibo)

    if fecha_pago <= fecha_inicio:
        fecha_pago = crear_fecha_recibo(siguiente_mes(fecha_inicio), dia_recibo)

    fecha_anterior = fecha_inicio

    datos = []
    mes = 1

    if tipo_calculo == "Vitesse":
        cuota = (capital * Decimal(str(valor)) / Decimal("100")).quantize(Decimal("0.01"),ROUND_HALF_UP)

    else:
        cuota = Decimal(str(valor)).quantize(Decimal("0.01"),ROUND_HALF_UP)

    while saldo > 0:

        amorts_periodo = []

        for _, row in df_amort.iterrows():

            if pd.isna(row["Fecha"]):
                continue

            fecha_a = pd.to_datetime(row["Fecha"]).date()
            importe_a = row["Importe (€)"]

            if fecha_anterior <= fecha_a <= fecha_pago:
                amorts_periodo.append((fecha_a, importe_a))

        amorts_periodo.sort()

        if len(amorts_periodo) > 0:

            interes, saldo = interes_con_amortizaciones(
                saldo,
                tin,
                fecha_anterior,
                fecha_pago,
                amorts_periodo
            )

            amort_extra = sum(a[1] for a in amorts_periodo)

        else:

            interes = interes_periodo(
                saldo,
                tin,
                fecha_anterior,
                fecha_pago
            )

            amort_extra = 0

        interes = interes.quantize(Decimal("0.01"),ROUND_HALF_UP)

        seguro = ((saldo + interes) * seguro_tasa).quantize(Decimal("0.01"),ROUND_HALF_UP)

        if saldo + interes <= cuota:

            amort = saldo
            saldo = Decimal("0")
            cuota_final = amort + interes

        else:

            amort = cuota - interes
            saldo = saldo - amort
            cuota_final = cuota

        datos.append({

            "Mes": mes,
            "Fecha recibo": fecha_pago,
            "Capital pendiente (€)": float(saldo + amort),
            "Cuota (€)": float(cuota_final),
            "Intereses (€)": float(interes),
            "Amortización (€)": float(amort),
            "Amortización anticipada (€)": float(amort_extra),
            "Saldo (€)": float(saldo),
            "Seguro (€)": float(seguro),
            "Recibo total (€)": float(cuota_final + seguro)

        })

        fecha_anterior = fecha_pago
        fecha_pago = crear_fecha_recibo(siguiente_mes(fecha_pago), dia_recibo)

        mes += 1

        if mes > 600:
            break

    return pd.DataFrame(datos)


# ---------------------------------------------------------
# CALCULO TAE
# ---------------------------------------------------------

def calcular_tae(cuotas, fechas):

    tiempos=[0.0]

    for i in range(1,len(fechas)):

        f0=fechas[i-1]
        f1=fechas[i]

        fraccion=(f1-f0).days/dias_ano(f0)
        tiempos.append(tiempos[-1]+fraccion)

    def van(tasa):
        return sum(c/((1+tasa)**t) for c,t in zip(cuotas,tiempos))

    minimo=-0.9999
    maximo=10

    for _ in range(1000):

        medio=(minimo+maximo)/2
        valor=van(medio)

        if abs(valor)<1e-10:
            return round(medio*100,2)

        if valor>0:
            minimo=medio
        else:
            maximo=medio

    return round(medio*100,2)


# ---------------------------------------------------------
# INPUTS
# ---------------------------------------------------------

capital = st.number_input("Capital pendiente (€)",0.0,1000000.0,6000.0)

tin = st.number_input("TIN anual (%)",0.0,100.0,21.79)

fecha_inicio = st.date_input("Fecha inicio",datetime.today())

dia_recibo = st.selectbox("Día del recibo", list(range(1,29)))

tipo_calculo = st.selectbox("Tipo cálculo",["Vitesse","Cuota"])

valor = st.number_input("Valor cálculo",0.0,1000.0,3.0)

# ---------------------------------------------------------
# AMORTIZACIONES
# ---------------------------------------------------------

st.subheader("Amortizaciones anticipadas")

df_amort = st.data_editor(
    pd.DataFrame({
        "Fecha": [None],
        "Importe (€)": [0.0]
    }),
    column_config={
        "Fecha": st.column_config.DateColumn("Fecha amortización",format="DD/MM/YYYY"),
        "Importe (€)": st.column_config.NumberColumn("Importe (€)",min_value=0,step=100)
    },
    num_rows="dynamic",
    use_container_width=True
)

# ---------------------------------------------------------
# SEGURO
# ---------------------------------------------------------

opciones_seguro={
"No":0,
"Un titular Light":0.0035,
"Un titular Full/Senior":0.0061,
"Dos titulares Full/Full":0.0104,
"Dos titulares Light/Light":0.0059
}

seguro_str=st.selectbox("Seguro",list(opciones_seguro.keys()))
seguro_tasa=opciones_seguro[seguro_str]

# ---------------------------------------------------------
# CALCULAR
# ---------------------------------------------------------

if st.button("Calcular"):

    tabla=simulador(
        capital,
        tin,
        tipo_calculo,
        valor,
        fecha_inicio,
        dia_recibo,
        df_amort,
        seguro_tasa
    )

    st.dataframe(tabla,use_container_width=True)

    # -------- FLUJOS TAE --------

    flujos=[]
    fechas_flujos=[]

    flujos.append(-capital)
    fechas_flujos.append(fecha_inicio)

    for i,row in tabla.iterrows():
        flujos.append(row["Recibo total (€)"])
        fechas_flujos.append(row["Fecha recibo"])

    for _,row in df_amort.iterrows():

        if pd.isna(row["Fecha"]):
            continue

        flujos.append(row["Importe (€)"])
        fechas_flujos.append(pd.to_datetime(row["Fecha"]).date())

    datos_tae=list(zip(fechas_flujos,flujos))
    datos_tae.sort()

    fechas_flujos=[x[0] for x in datos_tae]
    flujos=[x[1] for x in datos_tae]

    tae=calcular_tae(flujos,fechas_flujos)

    total_intereses=round(tabla["Intereses (€)"].sum(),2)
    total_seguro=round(tabla["Seguro (€)"].sum(),2)
    total_pago=round(tabla["Recibo total (€)"].sum(),2)

    resumen=pd.DataFrame({

        "Concepto":[
        "Duración (meses)",
        "Intereses (€)",
        "Seguro (€)",
        "Total pagado (€)",
        "TAE (%)"
        ],

        "Valor":[
        len(tabla),
        total_intereses,
        total_seguro,
        total_pago,
        tae
        ]

    })

    st.subheader("Resumen")
    st.table(resumen)

    output = BytesIO()

    with pd.ExcelWriter(output) as writer:
        tabla.to_excel(writer,index=False)
        resumen.to_excel(writer,sheet_name="Resumen",index=False)

    st.download_button(
        "📥 Descargar Excel",
        output.getvalue(),
        "simulacion_revolving.xlsx"
    )
