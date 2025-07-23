from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import logging

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes to allow Chrome extension to call this API
# More permissive CORS configuration for debugging
CORS(app, 
     origins=["*"],  # Allow all origins for now
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     supports_credentials=False)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Salesforce API configuration
SALESFORCE_API_VERSION = "v58.0"

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "Salesforce API Proxy",
        "version": "1.0.0",
        "endpoints": [
            "/api/query",
            "/api/describe/<object_name>",
            "/api/sobjects/<object_name>",
            "/api/sobjects/<object_name>/<record_id>",
            "/api/proxy"
        ]
    })

@app.route('/debug', methods=['GET'])
def debug_info():
    """Debug endpoint to check app status"""
    import sys
    return jsonify({
        "status": "Flask app is running",
        "python_version": sys.version,
        "flask_version": app.__class__.__module__,
        "registered_routes": [str(rule) for rule in app.url_map.iter_rules()],
        "request_method": "GET",
        "cors_enabled": True
    })

@app.route('/api/query', methods=['POST', 'OPTIONS'])
def proxy_query():
    """Proxy SOQL queries to Salesforce"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'query' not in data or 'instanceUrl' not in data or 'sessionId' not in data:
            return jsonify({
                "error": "Missing required fields: query, instanceUrl, sessionId"
            }), 400
        
        query = data['query']
        instance_url = data['instanceUrl']
        session_id = data['sessionId']
        
        # Prepare Salesforce API request
        sf_url = f"{instance_url}/services/data/{SALESFORCE_API_VERSION}/query/"
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        params = {'q': query}
        
        logger.info(f"Executing SOQL query: {query[:100]}...")
        logger.info(f"Target URL: {sf_url}")
        logger.info(f"Session ID prefix: {session_id[:10]}...")
        
        # Make request to Salesforce
        try:
            response = requests.get(sf_url, headers=headers, params=params, timeout=30)
            logger.info(f"Salesforce response status: {response.status_code}")
        except requests.exceptions.ProxyError as e:
            logger.error(f"Proxy error - PythonAnywhere free tier restriction: {e}")
            return jsonify({
                "error": "External API access restricted",
                "message": "PythonAnywhere free tier doesn't allow external HTTPS requests to Salesforce. You need to upgrade to a paid plan.",
                "details": str(e),
                "solution": "Upgrade to PythonAnywhere Hacker plan ($5/month) to enable external API calls"
            }), 403
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return jsonify({
                "error": "Network error",
                "message": str(e),
                "type": type(e).__name__
            }), 500
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Query successful: {result.get('totalSize', 0)} records returned")
            return jsonify(result)
        else:
            logger.error(f"Salesforce API error: {response.status_code} - {response.text}")
            return jsonify({
                "error": f"Salesforce API error: {response.status_code}",
                "details": response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({"error": "Request timeout"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({"error": f"Request error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/describe/<object_name>', methods=['POST', 'OPTIONS'])
def proxy_describe(object_name):
    """Proxy object describe calls to Salesforce"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'instanceUrl' not in data or 'sessionId' not in data:
            return jsonify({
                "error": "Missing required fields: instanceUrl, sessionId"
            }), 400
        
        instance_url = data['instanceUrl']
        session_id = data['sessionId']
        
        # Prepare Salesforce API request
        sf_url = f"{instance_url}/services/data/{SALESFORCE_API_VERSION}/sobjects/{object_name}/describe/"
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        logger.info(f"Describing object: {object_name}")
        logger.info(f"Target URL: {sf_url}")
        
        # Make request to Salesforce
        try:
            response = requests.get(sf_url, headers=headers, timeout=30)
            logger.info(f"Salesforce response status: {response.status_code}")
        except requests.exceptions.ProxyError as e:
            logger.error(f"Proxy error - PythonAnywhere free tier restriction: {e}")
            return jsonify({
                "error": "External API access restricted",
                "message": "PythonAnywhere free tier doesn't allow external HTTPS requests to Salesforce. You need to upgrade to a paid plan.",
                "details": str(e),
                "solution": "Upgrade to PythonAnywhere Hacker plan ($5/month) to enable external API calls"
            }), 403
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return jsonify({
                "error": "Network error",
                "message": str(e),
                "type": type(e).__name__
            }), 500
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Describe successful for {object_name}: {len(result.get('fields', []))} fields")
            return jsonify(result)
        else:
            logger.error(f"Salesforce API error: {response.status_code} - {response.text}")
            return jsonify({
                "error": f"Salesforce API error: {response.status_code}",
                "details": response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({"error": "Request timeout"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({"error": f"Request error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/sobjects/<object_name>', methods=['POST', 'OPTIONS'])
def proxy_create_record(object_name):
    """Proxy record creation to Salesforce"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'instanceUrl' not in data or 'sessionId' not in data or 'recordData' not in data:
            return jsonify({
                "error": "Missing required fields: instanceUrl, sessionId, recordData"
            }), 400
        
        instance_url = data['instanceUrl']
        session_id = data['sessionId']
        record_data = data['recordData']
        
        # Prepare Salesforce API request
        sf_url = f"{instance_url}/services/data/{SALESFORCE_API_VERSION}/sobjects/{object_name}/"
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        logger.info(f"Creating record in {object_name}")
        
        # Make request to Salesforce
        response = requests.post(sf_url, headers=headers, json=record_data, timeout=30)
        
        if response.status_code in [200, 201]:
            result = response.json()
            logger.info(f"Record created successfully: {result.get('id')}")
            return jsonify(result)
        else:
            logger.error(f"Salesforce API error: {response.status_code} - {response.text}")
            return jsonify({
                "error": f"Salesforce API error: {response.status_code}",
                "details": response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({"error": "Request timeout"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({"error": f"Request error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/api/sobjects/<object_name>/<record_id>', methods=['GET', 'PATCH', 'DELETE', 'OPTIONS'])
def proxy_record_operations(object_name, record_id):
    """Proxy record operations (get, update, delete) to Salesforce"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        if 'instanceUrl' not in data or 'sessionId' not in data:
            return jsonify({
                "error": "Missing required fields: instanceUrl, sessionId"
            }), 400
        
        instance_url = data['instanceUrl']
        session_id = data['sessionId']
        
        # Prepare Salesforce API request
        sf_url = f"{instance_url}/services/data/{SALESFORCE_API_VERSION}/sobjects/{object_name}/{record_id}"
        headers = {
            'Authorization': f'Bearer {session_id}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        logger.info(f"{request.method} operation on {object_name} record: {record_id}")
        
        # Make request to Salesforce based on HTTP method
        if request.method == 'GET':
            response = requests.get(sf_url, headers=headers, timeout=30)
        elif request.method == 'PATCH':
            record_data = data.get('recordData', {})
            response = requests.patch(sf_url, headers=headers, json=record_data, timeout=30)
        elif request.method == 'DELETE':
            response = requests.delete(sf_url, headers=headers, timeout=30)
        
        if response.status_code in [200, 204]:
            if response.content:
                result = response.json()
                logger.info(f"Operation successful")
                return jsonify(result)
            else:
                return jsonify({"success": True})
        else:
            logger.error(f"Salesforce API error: {response.status_code} - {response.text}")
            return jsonify({
                "error": f"Salesforce API error: {response.status_code}",
                "details": response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({"error": "Request timeout"}), 504
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return jsonify({"error": f"Request error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

def handle_preflight():
    """Handle CORS preflight requests"""
    response = jsonify({"status": "ok"})
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization,X-Requested-With")
    response.headers.add("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS,PATCH")
    response.headers.add("Access-Control-Max-Age", "3600")
    return response

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": [
            "GET / - Health check",
            "POST /api/query - Execute SOQL query",
            "POST /api/describe/<object_name> - Get object metadata",
            "POST /api/sobjects/<object_name> - Create record",
            "GET /api/sobjects/<object_name>/<record_id> - Get record",
            "PATCH /api/sobjects/<object_name>/<record_id> - Update record",
            "DELETE /api/sobjects/<object_name>/<record_id> - Delete record",
            "POST /api/proxy - General proxy for any Salesforce API call"
        ]
    }), 404

@app.route('/api/proxy', methods=['POST', 'OPTIONS'])
def general_proxy():
    """General proxy endpoint for any Salesforce API call"""
    if request.method == 'OPTIONS':
        return handle_preflight()
    
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['instance_url', 'endpoint', 'auth_token']
        if not data or not all(field in data for field in required_fields):
            return jsonify({
                "error": f"Missing required fields: {', '.join(required_fields)}"
            }), 400
        
        instance_url = data['instance_url']
        endpoint = data['endpoint']
        auth_token = data['auth_token']
        method = data.get('method', 'GET').upper()
        body = data.get('body')
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Construct full URL
        url = f"{instance_url.rstrip('/')}{endpoint}"
        
        logger.info(f"Proxying {method} request to: {url}")
        
        # Make the request
        if method == 'GET':
            response = requests.get(url, headers=headers, timeout=30)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=body, timeout=30)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=body, timeout=30)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            return jsonify({"error": f"Unsupported HTTP method: {method}"}), 400
        
        # Handle response
        if response.status_code == 200 or response.status_code == 201:
            try:
                return jsonify(response.json())
            except ValueError:
                return response.text
        else:
            logger.error(f"Salesforce API error: {response.status_code} - {response.text}")
            try:
                error_data = response.json()
                return jsonify({
                    "error": "Salesforce API error",
                    "status_code": response.status_code,
                    "details": error_data
                }), response.status_code
            except ValueError:
                return jsonify({
                    "error": "Salesforce API error",
                    "status_code": response.status_code,
                    "message": response.text
                }), response.status_code
                
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        return jsonify({"error": "Request timeout"}), 408
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Unexpected error in general_proxy: {e}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Internal server error",
        "message": "Please check the server logs for more details"
    }), 500

if __name__ == '__main__':
    # For local development
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
