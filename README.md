# Glenique E-Commerce Platform

A full-stack, multi-vendor e-commerce platform built using Python, Flask, and MongoDB.

## Key Features
- **Role-Based Access:** Dedicated interfaces for Users (Shoppers), Merchants, and Admins.
- **Merchant Dashboard:** Complete control for merchants to manage inventory, add products, process orders, and track revenue.
- **User Experience:** Seamless product browsing, search functionality, dynamic cart management, and wishlists.
- **Real-time Alerts:** Low stock alerts and new order notifications for merchants.
- **Admin Analytics:** Tools to monitor overall sales and platform performance.

## Tech Stack
- **Backend:** Python, Flask, Werkzeug
- **Database:** MongoDB (PyMongo)
- **Frontend:** HTML5, CSS3, Jinja2 Templates
- **Deployment:** Configured for Vercel Serverless Functions

## Local Setup
1. Ensure you have Python and MongoDB installed.
2. Install the necessary packages via `pip install -r requirements.txt`.
3. Set up your environment variables:
   - `DATABASE_URL`: Your MongoDB connection string (defaults to `mongodb://localhost:27017/`).
   - `NAME`: The name of the platform.
4. Run the app: `python app.py`
5. Open your browser and navigate to `http://localhost:80`.

## Vercel Deployment
The included `vercel.json` routes the Flask application to Vercel's Python runtime while safely serving assets directly from the `/static` directory.