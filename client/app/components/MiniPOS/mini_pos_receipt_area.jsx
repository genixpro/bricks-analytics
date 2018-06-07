import React from 'react';
import ContentWrapper from '../Layout/ContentWrapper';
import {Button, Grid, Row, Col, Dropdown, MenuItem, Well, Table, Checkbox} from 'react-bootstrap';
import _ from 'underscore';
import NumberFormat from 'react-number-format';


class MiniPosReceiptArea extends React.Component {
    constructor() {
        super();
    }

    render() {
        return (
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
                                this.props.items.map((item, index) =>
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
                        <h3>Subtotal&nbsp;&nbsp;&nbsp;<NumberFormat value={this.props.subtotal} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h3>
                        <h3>Taxes&nbsp;&nbsp;&nbsp;<NumberFormat value={this.props.taxes} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h3>
                        <h2>Total&nbsp;&nbsp;&nbsp;<NumberFormat value={this.props.total} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} /></h2>
                    </Col>
                </Row>
            </Well>
        );
    }
}

export default MiniPosReceiptArea;
