/**
 * INVENTORY UPDATES
 * Handles updating the stock quantity via AJAX
 */
async function updateStock(productId) {
    // Finds the specific input field for this product (e.g., id="stock-123")
    const stockInput = document.getElementById(`stock-${productId}`);
    if (!stockInput) {
        console.error("Could not find input field for ID:", productId);
        return;
    }
    
    const newStock = stockInput.value;

    try {
        const response = await fetch('/inventory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                id: productId,
                stock: newStock
            })
        });

        // Check if the server actually returned JSON
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const result = await response.json();
            if (response.ok) {
                alert("✅ Stock updated successfully!");
                location.reload(); 
            } else {
                alert("❌ Error: " + (result.message || "Failed to update"));
            }
        } else {
            throw new Error("Server returned non-JSON response. Check app.py routes.");
        }
    } catch (error) {
        console.error("Update Error:", error);
        alert("System error. Please check the console.");
    }
}

/**
 * DELETE PRODUCT
 * Removes a product from Supabase via the inventory route
 */
async function deleteProduct(productId) {
    if (!confirm("⚠️ Are you sure you want to delete this product? This cannot be undone.")) return;

    try {
        const response = await fetch('/inventory', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                delete_id: productId
            })
        });

        const contentType = response.headers.get("content-type");
        if (contentType && contentType.indexOf("application/json") !== -1) {
            const result = await response.json();
            if (response.ok) {
                alert("🗑️ Product deleted!");
                location.reload();
            } else {
                alert("❌ Error: " + result.message);
            }
        }
    } catch (error) {
        console.error("Delete Error:", error);
        alert("Failed to delete product.");
    }
}

/**
 * RECORD SALE
 * Records a transaction and reduces stock automatically
 */
async function recordSale(event) {
    if (event) event.preventDefault(); 

    const productSelect = document.getElementById('product_id');
    const quantityInput = document.getElementById('quantity');

    if (!productSelect.value || !quantityInput.value) {
        alert("Please select a product and quantity");
        return;
    }

    const data = {
        product_id: productSelect.value,
        quantity: quantityInput.value
    };

    try {
        const response = await fetch('/sales', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            alert("💰 Sale recorded successfully!");
            window.location.href = '/sales'; 
        } else {
            alert("❌ Sale failed: " + result.message);
        }
    } catch (error) {
        console.error("Sales Error:", error);
        alert("Connection error. Check your backend.");
    }
}

/**
 * INITIALIZE DYNAMIC UI
 */
document.addEventListener('DOMContentLoaded', () => {
    // Attach event listener to the Sales form
    const salesForm = document.getElementById('sales-form');
    if (salesForm) {
        salesForm.addEventListener('submit', recordSale);
    }
    
    // Check for "Low Stock" items and highlight them if needed
    const stockInputs = document.querySelectorAll('input[id^="stock-"]');
    stockInputs.forEach(input => {
        if (parseInt(input.value) <= 10) {
            input.style.borderColor = "red";
            input.style.backgroundColor = "#fff0f0";
        }
    });
});