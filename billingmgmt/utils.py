def calculate_gst_split(amount, gst_percent):
    """
    Returns CGST amount, SGST amount, Total GST
    """
    total_gst = (amount * gst_percent) / 100
    cgst = total_gst / 2
    sgst = total_gst / 2
    return cgst, sgst, total_gst
