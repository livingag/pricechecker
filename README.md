# pricechecker
Checks whether products are on sale at Woolworths or Coles

## Installation

Create a virtual environment using `requirements.txt` and just run the script! It will scrape the Woolworths and Coles APIs for prices of products contained in the `products.yaml` file and notify you of the specials through an email. Schedule the script to be run every Wednesday (when the specials get changed) to be notified if any of your configured products are on sale for the week.

## Configuration

Edit the `GMAIL_ADDRESS` and `GMAIL_PASSWORD` variables in `pricechecker.py` in order to use email notifications.

`products.yaml` shows an example product configuration. The product IDs are visible in both the Woolworths and Coles product page URLs:

<pre>
https://www.woolworths.com.au/shop/productdetails/<b>36066</b>/arnott-s-tim-tam-original-chocolate-biscuits

https://www.coles.com.au/product/arnotts-tim-tam-chocolate-biscuits-original-200g-<b>329607</b>
</pre>
