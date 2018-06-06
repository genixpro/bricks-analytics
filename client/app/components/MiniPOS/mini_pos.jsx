import React from 'react';
import ContentWrapper from '../Layout/ContentWrapper';
import {Grid, Row, Col, Dropdown, MenuItem, Well, Table} from 'react-bootstrap';
import _ from 'underscore';
import NumberFormat from 'react-number-format';

class MiniPos extends React.Component {
    constructor() {
        super();
        this.state = {
            items: [],
            subtotal: 0,
            taxes: 0,
            total: 0
        }
    }


    onReceiptAreaClicked()
    {
        const elem = document.getElementById('receipt-barcode-input');
        elem.focus();
    }



    barcodeChanged(event)
    {
        const barcodeNumber = event.target.value;
        this.setState({barcode: barcodeNumber});
    }


    onBarcodeSubmit(event)
    {
        event.preventDefault();

        const barcodeNumber = this.state.barcode;

        if (barcodeNumber) {

            // First check to see if there are any items already matching this barcode
            const existingItem = _.findWhere(this.state.items, {"barcode": barcodeNumber});

            if (existingItem) {
                existingItem.quantity += 1;

                const newItems = this.state.items.concat([]);
                this.updateTotals(newItems);
                this.setState({items: newItems, barcode: ""});
            }
            else {
                let newItem = null;
                if (barcodeNumber === "1") {
                    newItem = {
                        "name": "onion",
                        "price": 3.99,
                        "quantity": 1,
                        "barcode": barcodeNumber
                    }
                }

                if (newItem) {
                    const newItems = this.state.items.concat([newItem]);
                    this.updateTotals(newItems);
                    this.setState({items: newItems, barcode: ""});
                }
                else {
                    this.setState({barcode: ""});
                    alert("We have no item with this barcode.");
                }
            }
        }
    }


    updateTotals(items)
    {
        let subtotal = 0;
        items.forEach((item) => {
            subtotal += item.price * item.quantity;
        });

        const taxes = subtotal * 0.13;

        const total = subtotal + taxes;

        this.setState({
            subtotal: subtotal,
            taxes: taxes,
            total: total
        })
    }


    render() {
        return (
            <Grid fluid={true} className={"mini_pos"} onClick={this.onReceiptAreaClicked.bind(this)}>
                <Well bsSize="large" className={"receipt-well"}>
                    <Row className={"receipt-header"}>
                        <Col xs={12}>
                            <div className={"date"}>{new Date().toString()}</div>
                        </Col>
                    </Row>
                    <Row className={"receipt-body"}>
                        <Col xs={12}>
                            <Table striped bordered condensed hover>
                                <thead>
                                    <tr>
                                        <th className={"name-column"}>Name</th>
                                        <th className={"quantity-column"}>Quantity</th>
                                        <th className={"each-column"}>Each</th>
                                        <th className={"total-column"}>Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {
                                        this.state.items.map((item, index) =>
                                        {
                                          return <tr key={index}>
                                                <td className={"name-column"}>{item.name}</td>
                                                <td className={"quantity-column"}>{item.quantity}</td>
                                                <td className={"each-column"}><NumberFormat value={item.price} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></td>
                                                <td className={"total-column"}><NumberFormat value={item.price * item.quantity} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></td>
                                            </tr>;
                                        })
                                    }
                                </tbody>
                            </Table>
                        </Col>
                    </Row>
                    <Row className={"receipt-total-row"}>
                        <Col xs={4} xsOffset={8}>
                            <h3>Subtotal&nbsp;&nbsp;&nbsp;<NumberFormat value={this.state.subtotal} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h3>
                            <h3>Taxes&nbsp;&nbsp;&nbsp;<NumberFormat value={this.state.taxes} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h3>
                            <h2>Total&nbsp;&nbsp;&nbsp;<NumberFormat value={this.state.total} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h2>
                        </Col>
                    </Row>
                </Well>
                <Well bsSize="large" className={"ad-well"}>
                    <h1>Mini POS</h1>
                    <img src={"/img/loblaws_logo.svg"} />
                </Well>
                <div className={"receipt-barcode-input-wrapper"}>
                    <form onSubmit={this.onBarcodeSubmit.bind(this)} action="#">
                        <input type={"text"} id={'receipt-barcode-input'} value={this.state.barcode} onChange={this.barcodeChanged.bind(this)} />
                    </form>
                </div>
            </Grid>
        );
    }
}

export default MiniPos;
