from flask import Flask, jsonify, request, send_from_directory
import xmlrpc.client
import os

app = Flask(__name__)

username = os.environ.get('ODOO_USER')
password = os.environ.get('ODOO_PASSWORD')
url = os.environ.get('ODOO_URL')
db = os.environ.get('ODOO_DB')
home_latlong = os.environ.get('HOME_LATLONG')

def get_geo(address):
    import geocoder
    geo = geocoder.google(address)
    return geo.latlng

def get_odoo_models_uid():
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
    common.version()

    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
    return models, uid

@app.route('/')
def index():
    return send_from_directory('', 'index.html')

@app.route('/pendingdeliveries', methods=['GET'])
def get_pending_deliveries():
    # Filter deliveries to get only the pending ones
    pending_deliveries={}
    
    models,uid  = get_odoo_models_uid()

    # print(models.execute_kw(db, uid, password, 'res.partner', 'search', [[['is_company', '=', True]]]))
    ordenes_pendientes_ids = models.execute_kw(db, uid, password, 'stock.picking', 'search', [[['state', '=', 'assigned']]])
    ordenes_pendientes = models.execute_kw(db, uid, password, 'stock.picking', 'read', [ordenes_pendientes_ids])
    lat_longs=[]
    deliveries = []
    for orden_pendiente in ordenes_pendientes:
        pos_order_id = orden_pendiente["pos_order_id"][0]
        pos_order = models.execute_kw(db, uid, password, 'pos.order', 'read', [pos_order_id])[0]
        referencia_orden =  pos_order["pos_reference"] # referencia de orden
        ticket_number = pos_order["tracking_number"] # numero de ticket
        order_id = orden_pendiente["id"]
        order_name = orden_pendiente["name"] #order name desde warehouse
        order_origin = orden_pendiente["origin"] #order name desde Point of Sale
        partner = models.execute_kw(db, uid, password, 'res.partner', 'read', [orden_pendiente["message_partner_ids"]])[0]
        nombre = partner["complete_name"]
        street1 = partner["street"]
        street2 = partner["street2"]
        mobile = partner["phone_sanitized"]
        address = partner["contact_address_inline"]
        lat,long = partner["partner_latitude"], partner["partner_longitude"]
        if partner["partner_latitude"] == 0 or partner["partner_longitude"] == 0:
            lat,long = get_geo(address)
            lat_longs.append(f"{lat},{long}")
            models.execute_kw(db, uid, password, 'res.partner', 'write', [[partner["id"]], {'partner_latitude': lat, 'partner_longitude': long}])
        else:
            
            lat_longs.append(f"{partner['partner_latitude']},{partner['partner_longitude']}")
            
        print(f"{ticket_number=} {referencia_orden=} {nombre=} {mobile=} {address=} {lat=} {long=}")
        deliveries.append({
            "order_id": order_id,
            "ticket_number": ticket_number,
            "referencia_orden": referencia_orden,
            "nombre_cliente": nombre,
            "telefono": mobile,
            "direccion": address,
            "lat": lat,
            "long": long,
        })
    pending_deliveries["deliveries"] = deliveries
    pending_deliveries["google_map"] = f"https://www.google.com/maps/dir/{home_latlong}/{'/'.join(lat_longs)}/{home_latlong}/"


    return jsonify(pending_deliveries)

@app.route('/deliverycompleted', methods=['POST'])
def mark_delivery_completed():
    data = request.get_json()
    delivery_id = data.get('id')
    models,uid  = get_odoo_models_uid()
    models.execute_kw(db, uid, password, 'stock.picking', 'write', [[delivery_id], {'state': 'done'}])

    return jsonify({"message": "Delivery marked as completed"}), 200
    

if __name__ == '__main__':
    app.run(port=6069)


