"""Catálogo de entidades financieras de Colombia.

`domain` sirve para traer el logo (favicon) en el frontend; si no carga,
el frontend muestra un monograma con `color`. Para una entidad que no esté
aquí, la cuenta se crea con `institution_name` libre.
"""

BANCOS = "Bancos"
BILLETERAS = "Billeteras y neobancos"
INVERSION = "Inversión, fondos y pensiones"
OTROS = "Pagos y cripto"

_RAW = [
    # slug, nombre, categoría, dominio, color de marca (aprox.)
    ("bancolombia", "Bancolombia", BANCOS, "bancolombia.com", "#FDDA24"),
    ("davivienda", "Davivienda", BANCOS, "davivienda.com", "#E1141E"),
    ("bbva", "BBVA Colombia", BANCOS, "bbva.com.co", "#004481"),
    ("banco-bogota", "Banco de Bogotá", BANCOS, "bancodebogota.com", "#0B3C8C"),
    ("banco-popular", "Banco Popular", BANCOS, "bancopopular.com.co", "#00A651"),
    ("banco-occidente", "Banco de Occidente", BANCOS, "bancodeoccidente.com.co", "#0072BC"),
    ("av-villas", "AV Villas", BANCOS, "avvillas.com.co", "#0C5BA8"),
    ("scotiabank-colpatria", "Scotiabank Colpatria", BANCOS, "scotiabankcolpatria.com", "#EC111A"),
    ("itau", "Itaú", BANCOS, "itau.co", "#EC7000"),
    ("caja-social", "Banco Caja Social", BANCOS, "bancocajasocial.com", "#0B6AB0"),
    ("gnb-sudameris", "GNB Sudameris", BANCOS, "gnbsudameris.com.co", "#E4002B"),
    ("bancoomeva", "Bancoomeva", BANCOS, "bancoomeva.com.co", "#00843D"),
    ("banco-falabella", "Banco Falabella", BANCOS, "bancofalabella.com.co", "#6CB33F"),
    ("banco-pichincha", "Banco Pichincha", BANCOS, "bancopichincha.com.co", "#FFD100"),
    ("banco-agrario", "Banco Agrario", BANCOS, "bancoagrario.gov.co", "#00793B"),
    ("banco-w", "Banco W", BANCOS, "bancow.com.co", "#F58220"),
    ("mibanco", "Mibanco", BANCOS, "mibanco.com.co", "#00A0DF"),
    ("finandina", "Banco Finandina", BANCOS, "bancofinandina.com", "#003D7C"),
    ("bancamia", "Bancamía", BANCOS, "bancamia.com.co", "#E2231A"),
    ("serfinanza", "Banco Serfinanza", BANCOS, "bancoserfinanza.com", "#E30613"),

    ("nequi", "Nequi", BILLETERAS, "nequi.com.co", "#DA0081"),
    ("daviplata", "Daviplata", BILLETERAS, "daviplata.com", "#ED1C27"),
    ("nu", "Nu Colombia", BILLETERAS, "nu.com.co", "#820AD1"),
    ("lulo", "Lulo Bank", BILLETERAS, "lulobank.com", "#D6F23E"),
    ("rappipay", "RappiPay", BILLETERAS, "rappipay.co", "#FF441F"),
    ("dale", "Dale!", BILLETERAS, "dale.com.co", "#00B140"),
    ("movii", "Movii", BILLETERAS, "movii.com.co", "#6A2C91"),
    ("uala", "Ualá", BILLETERAS, "uala.com.co", "#1D4ED8"),

    ("hapi", "Hapi", INVERSION, "hapi.com", "#00C2A8"),
    ("trii", "Trii", INVERSION, "trii.co", "#5B2EFF"),
    ("tyba", "Tyba", INVERSION, "tyba.com.co", "#FF5A5F"),
    ("xtb", "XTB", INVERSION, "xtb.com", "#E4002B"),
    ("etoro", "eToro", INVERSION, "etoro.com", "#13C636"),
    ("fiduciaria-bancolombia", "Fiduciaria Bancolombia", INVERSION, "fiduciariabancolombia.com", "#FDDA24"),
    ("skandia", "Skandia", INVERSION, "skandia.co", "#00A651"),
    ("proteccion", "Protección", INVERSION, "proteccion.com", "#00A3E0"),
    ("porvenir", "Porvenir", INVERSION, "porvenir.com.co", "#F58220"),
    ("colfondos", "Colfondos", INVERSION, "colfondos.com.co", "#E4002B"),

    ("binance", "Binance", OTROS, "binance.com", "#F0B90B"),
    ("bitso", "Bitso", OTROS, "bitso.com", "#1E88E5"),
    ("paypal", "PayPal", OTROS, "paypal.com", "#003087"),
    ("wise", "Wise", OTROS, "wise.com", "#9FE870"),
]

INSTITUTIONS = [
    {"slug": s, "name": n, "category": c, "domain": d, "color": col}
    for s, n, c, d, col in _RAW
]
SLUGS = {i["slug"] for i in INSTITUTIONS}
