/*=========================================================
    AAYURKENDRA HMS
    STOCK ADD / EDIT
=========================================================*/

document.addEventListener("DOMContentLoaded", function () {
    const isEdit =
    document.getElementById("is_edit");

    /*=====================================================
        ELEMENTS
    =====================================================*/

    const medicineSearch = document.getElementById("medicineSearch");
    const medicineDropdown = document.getElementById("medicineDropdown");
    const medicineHidden = document.getElementById("id_medicine");

    const medicineName = document.getElementById("medicine_name");
    const medicineForm = document.getElementById("medicine_form");
    const medicineHSN = document.getElementById("medicine_hsn");
    const medicineGST = document.getElementById("medicine_gst");
    const medicineReorder = document.getElementById("medicine_reorder");
    const medicineExpiry = document.getElementById("medicine_expiry");

    /*=====================================================
        PURCHASE DETAILS
    =====================================================*/

    const packSize = document.getElementById("id_pack_size");
    const numberOfPacks = document.getElementById("id_number_of_packs");
    const purchasePrice = document.getElementById("id_unit_price");
    const sellingPrice = document.getElementById("id_selling_price");

    const baseUnit = document.getElementById("base_unit");

    /*=====================================================
        DATES
    =====================================================*/

    const manufactureDate = document.getElementById("manufacture_date");
    const expiryDate = document.getElementById("expiry_date");

    /*=====================================================
        CALCULATION OUTPUTS
    =====================================================*/

    const stockAdded = document.getElementById("stock_added");
    const unitPrice = document.getElementById("price_per_unit");
    const purchaseTotal = document.getElementById("purchase_total");

    const gstPercent = document.getElementById("gst_percent");
    const gstAmount = document.getElementById("gst_amount");
    const costAfterGST = document.getElementById("cost_after_gst");

    /*=====================================================
        SUMMARY
    =====================================================*/

    const currentStock = document.getElementById("current_stock");
    const addedStock = document.getElementById("added_stock");
    const totalStock = document.getElementById("total_stock");

    const purchaseCard = document.getElementById("purchase_price_card");
    const sellingCard = document.getElementById("selling_price_card");
    const profitCard = document.getElementById("profit_card");

    /*=====================================================
        SAFE VALUE
    =====================================================*/

    function num(value){

        value = parseFloat(value);

        return isNaN(value) ? 0 : value;

    }

    /*=====================================================
        SHOW DROPDOWN
    =====================================================*/

    if(medicineSearch && medicineDropdown){

        medicineSearch.addEventListener("focus",function(){

            medicineDropdown.style.display="block";

            filterMedicine();

        });

        medicineSearch.addEventListener("input",filterMedicine);

    }

    /*=====================================================
        FILTER MEDICINE
    =====================================================*/

    function filterMedicine(){

        if(!medicineSearch || !medicineDropdown) return;

        let keyword = medicineSearch.value.trim().toLowerCase();

        let found = 0;

        document.querySelectorAll(".medicine-item").forEach(function(item){

            let txt = (

                (item.dataset.name || "") +

                " " +

                (item.dataset.hsn || "") +

                " " +

                (item.dataset.form || "")

            ).toLowerCase();

            if(txt.includes(keyword)){

                item.style.display="";

                found++;

            }

            else{

                item.style.display="none";

            }

        });

        medicineDropdown.style.display =

            found ? "block" : "none";

    }

    /*=====================================================
        PART 2 STARTS BELOW
    =====================================================*/
        /*=====================================================
        SELECT MEDICINE
    =====================================================*/

    document.querySelectorAll(".medicine-item").forEach(function(item){

        item.addEventListener("click", function(){

            if(medicineHidden){

                medicineHidden.value=this.dataset.id || "";

                medicineHidden.dispatchEvent(
                    new Event("change")
                );

            }

            if(medicineSearch){

                medicineSearch.value=this.dataset.name || "";

            }

            if(medicineName){

                medicineName.value=this.dataset.name || "";

            }

            if(medicineForm){

                medicineForm.value=this.dataset.form || "";

            }

            if(medicineHSN){

                medicineHSN.value=this.dataset.hsn || "";

            }

            if(medicineGST){

                medicineGST.value=this.dataset.gst || "0";

            }

            if(medicineReorder){

                medicineReorder.value=this.dataset.reorder || "0";

            }

            if(medicineExpiry){

                medicineExpiry.value=
                    (this.dataset.expiry || "0") + " Days";

            }

            if(currentStock){

                currentStock.innerText=
                    this.dataset.stock || "0";

            }

            /*----------------------------------
                AUTO BASE UNIT
            ----------------------------------*/

            if(baseUnit){

                let form=
                    (this.dataset.form || "")
                    .toUpperCase();

                if(form==="LIQUID"){

                    baseUnit.value="ml";

                }

                else if(form==="POWDER"){

                    baseUnit.value="g";

                }

                else{

                    baseUnit.value="piece";

                }

            }

            medicineDropdown.style.display="none";

            let batch=document.getElementById("batch_number");

            if(batch){

                batch.focus();

            }

            calculate();

        });

    });

    /*=====================================================
        CLOSE DROPDOWN
    =====================================================*/

    document.addEventListener("click",function(e){

        if(
            medicineSearch &&
            medicineDropdown &&
            !medicineSearch.contains(e.target) &&
            !medicineDropdown.contains(e.target)
        ){

            medicineDropdown.style.display="none";

        }

    });

    /*=====================================================
        AUTO SELLING PRICE
    =====================================================*/

    if(purchasePrice && sellingPrice){

        purchasePrice.addEventListener("blur",function(){

            if(
                sellingPrice.value.trim()===""
                ||
                parseFloat(sellingPrice.value)==0
            ){

                sellingPrice.value=purchasePrice.value;

            }

            calculate();

        });

    }

    /*=====================================================
        EXPIRY VALIDATION
    =====================================================*/

    if(manufactureDate && expiryDate){

        expiryDate.addEventListener("change",function(){

            if(!manufactureDate.value)
                return;

            let mfg=
                new Date(manufactureDate.value);

            let exp=
                new Date(expiryDate.value);

            if(exp<=mfg){

                alert(
                    "Expiry Date must be greater than Manufacturing Date."
                );

                expiryDate.value="";

            }

        });

    }

    /*=====================================================
        PART 3 STARTS BELOW
    =====================================================*/
        /*=====================================================
        CALCULATE
    =====================================================*/

    function calculate(){

        const pack = num(packSize ? packSize.value : 0);

        const qty = num(numberOfPacks ? numberOfPacks.value : 0);

        const purchase = num(purchasePrice ? purchasePrice.value : 0);

        const selling = num(sellingPrice ? sellingPrice.value : 0);

        const gst = num(medicineGST ? medicineGST.value : 0);

        //------------------------------------------
        // STOCK
        //------------------------------------------

        const added = pack * qty;

        const current = num(
            currentStock ? currentStock.innerText : 0
        );

        //------------------------------------------
        // UNIT PRICE
        //------------------------------------------

        let perUnit = 0;

        if(pack > 0){

            perUnit = purchase / pack;

        }

        //------------------------------------------
        // PURCHASE
        //------------------------------------------

        const purchaseValue = purchase * qty;

        //------------------------------------------
        // GST
        //------------------------------------------

        const gstValue = purchaseValue * gst / 100;

        //------------------------------------------
        // COST
        //------------------------------------------

        const totalCost =
            purchaseValue + gstValue;

        //------------------------------------------
        // PROFIT
        //------------------------------------------

        const profit =
            selling - purchase;

        //------------------------------------------
        // AUTO OUTPUT
        //------------------------------------------

        if(stockAdded){

            stockAdded.value =
                added.toFixed(2);

        }

        if(unitPrice){

            unitPrice.value =
                perUnit.toFixed(4);

        }

        if (purchaseTotal) {

    const editMode =
        isEdit && isEdit.value === "1";

    purchaseTotal.value = editMode
        ? purchase.toFixed(2)
        : purchaseValue.toFixed(2);

}

        if(gstPercent){

            gstPercent.value =
                gst.toFixed(2)+" %";

        }

        if(gstAmount){

            gstAmount.value =
                gstValue.toFixed(2);

        }

        if (costAfterGST) {

    const editMode =
        isEdit && isEdit.value === "1";

    costAfterGST.value = editMode
        ? (purchase + (purchase * gst / 100)).toFixed(2)
        : totalCost.toFixed(2);

}

        //------------------------------------------
        // SUMMARY
        //------------------------------------------

        if(addedStock){

            addedStock.innerText =
                added.toFixed(2);

        }

        if (purchaseCard) {

    purchaseCard.innerText =
        purchase.toFixed(2);

}

        if(sellingCard){

            sellingCard.innerText =
                selling.toFixed(2);

        }

        if(profitCard){

            profitCard.innerText =
                profit.toFixed(2);

        }

        if (totalStock) {

            const editMode =
                isEdit && isEdit.value === "1";

            if (editMode) {

                totalStock.innerText =
                    current.toFixed(2);

            }
            else{

                totalStock.innerText =
                    (current + added).toFixed(2);

            }

        }

    }

    /*=====================================================
        LIVE EVENTS
    =====================================================*/

    [
        packSize,
        numberOfPacks,
        purchasePrice,
        sellingPrice
    ].forEach(function(input){

        if(!input) return;

        input.addEventListener(
            "input",
            calculate
        );

        input.addEventListener(
            "change",
            calculate
        );

    });

    /*=====================================================
        FORM VALIDATION
    =====================================================*/

    const form =
        document.querySelector("form");

    if(form){

        form.addEventListener("submit",function(e){

            if(
                medicineHidden &&
                medicineHidden.value === ""
            ){

                e.preventDefault();

                alert(
                    "Please select a medicine."
                );

                medicineSearch.focus();

                return;

            }

            if(
                purchasePrice &&
                num(purchasePrice.value)<=0
            ){

                e.preventDefault();

                alert(
                    "Purchase Price must be greater than zero."
                );

                purchasePrice.focus();

                return;

            }

            if(
                sellingPrice &&
                num(sellingPrice.value)<=0
            ){

                e.preventDefault();

                alert(
                    "Selling Price must be greater than zero."
                );

                sellingPrice.focus();

                return;

            }

        });

    }

    /*=====================================================
        ENTER KEY
    =====================================================*/

    document.querySelectorAll(
        "input,select"
    ).forEach(function(el){

        el.addEventListener(
            "keydown",
            function(e){

                if(e.key==="Enter"){

                    e.preventDefault();

                    const fields =
                        Array.from(
                            document.querySelectorAll(
                                "input,select,button"
                            )
                        );

                    const index =
                        fields.indexOf(this);

                    if(
                        index>-1 &&
                        index<fields.length-1
                    ){

                        fields[index+1].focus();

                    }

                }

            }
        );

    });

    /*=====================================================
        INITIAL LOAD
    =====================================================*/

    calculate();

});